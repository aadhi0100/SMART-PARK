import logging
from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from .database import get_db_connection_legacy as get_db_connection, get_loyalty_tier, get_peak_multiplier

logger = logging.getLogger(__name__)
core_bp = Blueprint('core', __name__)

# Updated locations for better slot distribution
LOCATIONS = [
    'Chennai Central', 'Marina Beach', 'T Nagar', 'Velachery', 'Adyar'
]

LOCATION_PREFIXES = {
    'Chennai Central': 'A', 'Marina Beach': 'B', 'T Nagar': 'C',
    'Velachery': 'D', 'Adyar': 'E'
}

TOTAL_SLOTS_PER_LOC = 10

@core_bp.route('/')
def index():
    return redirect(url_for('auth.login'))

@core_bp.route('/dashboard/<username>')
def dashboard(username):
    if session.get('username') != username:
        return redirect(url_for('auth.login'))
    conn = get_db_connection()
    try:
        total_bookings = conn.execute(
            "SELECT COUNT(*) FROM bookings WHERE username = ? AND status = 'active'", (username,)
        ).fetchone()[0]
        total_booked = conn.execute(
            "SELECT COUNT(*) FROM bookings WHERE status = 'active'"
        ).fetchone()[0]
        total_slots = len(LOCATIONS) * TOTAL_SLOTS_PER_LOC
        available_slots = max(0, total_slots - total_booked)
        revenue = None
        if session.get('role') == 'admin':
            revenue = conn.execute(
                "SELECT COALESCE(SUM(amount_paid), 0) FROM bookings"
            ).fetchone()[0]
        unread_count = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE username = ? AND is_read = 0", (username,)
        ).fetchone()[0]
        notifications = conn.execute(
            "SELECT * FROM notifications WHERE username = ? ORDER BY created_at DESC LIMIT 10", (username,)
        ).fetchall()
        user_row = conn.execute(
            "SELECT loyalty_points FROM users WHERE username = ?", (username,)
        ).fetchone()
        loyalty_pts = user_row['loyalty_points'] if user_row else 0
        spending_trend = conn.execute(
            "SELECT DATE(created_at) as day, COALESCE(SUM(amount_paid),0) as total "
            "FROM bookings WHERE username = ? AND created_at >= date('now','-7 days') "
            "GROUP BY day ORDER BY day",
            (username,)
        ).fetchall()
    finally:
        conn.close()

    tier = get_loyalty_tier(loyalty_pts)
    is_peak = get_peak_multiplier() > 1.0
    return render_template('dashboard.html', username=username,
                           total_bookings=total_bookings,
                           available_slots=available_slots,
                           total_slots=total_slots,
                           revenue=revenue,
                           role=session.get('role'),
                           unread_count=unread_count,
                           notifications=notifications,
                           loyalty_tier=tier,
                           is_peak=is_peak,
                           spending_trend=[dict(r) for r in spending_trend])

@core_bp.route('/profile/<username>', methods=['GET', 'POST'])
def profile(username):
    if session.get('username') != username:
        return redirect(url_for('auth.login'))

    msg = None
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            conn.execute(
                "UPDATE users SET email = ?, phone = ? WHERE username = ?", (email, phone, username)
            )
            conn.commit()
            msg = 'Profile updated successfully!'

        user = conn.execute(
            "SELECT id, username, role, created_at, email, phone, loyalty_points FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        total_bookings = conn.execute(
            "SELECT COUNT(*) FROM bookings WHERE username = ?", (username,)
        ).fetchone()[0]
        total_spent = conn.execute(
            "SELECT COALESCE(SUM(amount_paid), 0) FROM bookings WHERE username = ?", (username,)
        ).fetchone()[0]
        recent = conn.execute(
            "SELECT * FROM bookings WHERE username = ? ORDER BY created_at DESC LIMIT 5", (username,)
        ).fetchall()
    finally:
        conn.close()

    if user:
        loyalty_tier = get_loyalty_tier(user['loyalty_points'] or 0)
        return render_template('profile.html', username=username, user=user,
                               total_bookings=total_bookings, total_spent=total_spent,
                               recent_bookings=recent, msg=msg, loyalty_tier=loyalty_tier)
    return redirect(url_for('auth.login'))

@core_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

@core_bp.route('/ping')
def ping():
    return jsonify({'status': 'ok'}), 200

@core_bp.route('/api/slots')
def api_slots():
    """Get slot availability with better error handling"""
    try:
        conn = get_db_connection()
        try:
            booked_slots = conn.execute(
                "SELECT slot FROM bookings WHERE status = 'active'"
            ).fetchall()
            booked = [r[0] for r in booked_slots] if booked_slots else []
        finally:
            conn.close()

        result = {}
        for loc in LOCATIONS:
            prefix = LOCATION_PREFIXES[loc]
            # Count booked slots for this location
            loc_booked = [s for s in booked if s.startswith(prefix)]
            available = TOTAL_SLOTS_PER_LOC - len(loc_booked)
            
            result[loc] = {
                'booked': len(loc_booked),
                'available': max(0, available),  # Ensure non-negative
                'total': TOTAL_SLOTS_PER_LOC,
                'prefix': prefix
            }
        
        logger.info(f"Slot availability: {result}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting slot availability: {e}")
        # Return default availability if error
        result = {}
        for loc in LOCATIONS:
            result[loc] = {
                'booked': 0,
                'available': TOTAL_SLOTS_PER_LOC,
                'total': TOTAL_SLOTS_PER_LOC,
                'prefix': LOCATION_PREFIXES[loc]
            }
        return jsonify(result)

@core_bp.route('/api/notifications/<username>')
def api_notifications(username):
    if session.get('username') != username:
        return jsonify({'error': 'Unauthorized'}), 403
    conn = get_db_connection()
    try:
        notifs = conn.execute(
            "SELECT id, message, is_read, created_at FROM notifications "
            "WHERE username = ? ORDER BY created_at DESC LIMIT 20",
            (username,)
        ).fetchall()
    finally:
        conn.close()
    return jsonify([dict(n) for n in notifs])

@core_bp.route('/api/notifications/read/<username>', methods=['POST'])
def mark_notifications_read(username):
    if session.get('username') != username:
        return jsonify({'error': 'Unauthorized'}), 403
    conn = get_db_connection()
    try:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE username = ?", (username,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True})
