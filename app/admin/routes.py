import csv
import io
import logging

from flask import Blueprint, jsonify, make_response, redirect, render_template, request, session, url_for
from ..core.database import get_db_connection, add_notification, hash_password

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)

def require_admin():
    return session.get('role') != 'admin'

@admin_bp.route('/cctv/<username>')
def admin_cctv(username):
    if require_admin():
        return redirect(url_for('core.dashboard', username=username))
    return render_template('admin/admin_cctv.html', username=username)

@admin_bp.route('/users/<username>')
def admin_users(username):
    if require_admin():
        return redirect(url_for('core.dashboard', username=username))

    conn = get_db_connection()
    try:
        users_list = conn.execute(
            "SELECT id, username, role, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
        user_stats = conn.execute(
            "SELECT username, COUNT(*) as booking_count, COALESCE(SUM(amount_paid),0) as total_spent "
            "FROM bookings GROUP BY username ORDER BY booking_count DESC"
        ).fetchall()
        recent_bookings = conn.execute(
            "SELECT * FROM bookings ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
    finally:
        conn.close()
    return render_template('admin/admin_users.html', username=username,
                            users_list=users_list, user_stats=user_stats,
                            recent_bookings=recent_bookings)
@admin_bp.route('/reports/<username>')
def admin_reports(username):
    if require_admin():
        return redirect(url_for('core.dashboard', username=username))
    conn = get_db_connection()
    try:
        total_bookings = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
        active_bookings = conn.execute("SELECT COUNT(*) FROM bookings WHERE status = 'active'").fetchone()[0]
        cancelled_bookings = conn.execute("SELECT COUNT(*) FROM bookings WHERE status = 'cancelled'").fetchone()[0]
        completed_bookings = conn.execute("SELECT COUNT(*) FROM bookings WHERE status = 'completed'").fetchone()[0]
        total_users = conn.execute("SELECT COUNT(DISTINCT username) FROM bookings").fetchone()[0]
        total_revenue = conn.execute("SELECT COALESCE(SUM(amount_paid), 0) FROM bookings").fetchone()[0]
        popular_slots = conn.execute(
            "SELECT slot, COUNT(*) as count FROM bookings GROUP BY slot ORDER BY count DESC LIMIT 10").fetchall()
        revenue_by_vehicle = conn.execute(
            "SELECT vehicle, COUNT(*) as count, COALESCE(SUM(amount_paid),0) as revenue FROM bookings GROUP BY vehicle").fetchall()
        daily_revenue = conn.execute(
            "SELECT DATE(created_at) as day, COALESCE(SUM(amount_paid),0) as rev, COUNT(*) as cnt "
            "FROM bookings GROUP BY DATE(created_at) ORDER BY day DESC LIMIT 14").fetchall()
        hourly_dist = conn.execute(
            "SELECT strftime('%H', created_at) as hr, COUNT(*) as cnt FROM bookings GROUP BY hr ORDER BY hr"
        ).fetchall()
    finally:
        conn.close()

    return render_template('admin/admin_reports.html', username=username,
                           total_bookings=total_bookings, active_bookings=active_bookings,
                           cancelled_bookings=cancelled_bookings, completed_bookings=completed_bookings,
                           total_users=total_users, total_revenue=total_revenue,
                           popular_slots=[dict(r) for r in popular_slots],
                           revenue_by_vehicle=[dict(r) for r in revenue_by_vehicle],
                           daily_revenue=[dict(r) for r in daily_revenue],
                           hourly_dist=[dict(r) for r in hourly_dist])
@admin_bp.route('/create_user/<username>', methods=['GET', 'POST'])
def admin_create_user(username):
    if require_admin():
        return redirect(url_for('core.dashboard', username=username))
    msg = None
    error = None
    if request.method == 'POST':
        new_username = request.form.get('new_username', '').strip()
        role = request.form.get('role', 'user')
        password = request.form.get('password', '').strip()
        if not new_username or not password or role not in ['user', 'admin']:
            error = 'All fields are required.'
        elif len(password) < 6:
            error = 'Password must be at least 6 characters.'
        else:
            conn = get_db_connection()
            try:
                if conn.execute("SELECT id FROM users WHERE username = ?", (new_username,)).fetchone():
                    error = 'Username already exists.'
                else:
                    pw_hash = hash_password(password)
                    conn.execute(
                        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                        (new_username, pw_hash, role))
                    conn.commit()
                    add_notification(new_username, f"\U0001f44b Welcome! Your account was created by admin with role: {role}.")
                    msg = f'User "{new_username}" created successfully as {role}.'
            finally:
                conn.close()
    return render_template('admin/admin_create.html', username=username, msg=msg, error=error)

@admin_bp.route('/broadcast/<username>', methods=['POST'])
def admin_broadcast(username):
    if require_admin():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Invalid request'}), 400
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'success': False, 'message': 'Empty message'})
    conn = get_db_connection()
    try:
        users = conn.execute("SELECT username FROM users").fetchall()
        for u in users:
            conn.execute(
                "INSERT INTO notifications (username, message) VALUES (?, ?)",
                (u['username'], f"\U0001f4e2 Admin: {message}")
            )
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'message': f'Broadcast sent to {len(users)} users'})

@admin_bp.route('/change_role/<username>', methods=['POST'])
def admin_change_role(username):
    if require_admin():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Invalid request'}), 400
    target_username = data.get('target_username')
    new_role = data.get('new_role')

    if not target_username or new_role not in ['user', 'admin']:
        return jsonify({'success': False, 'message': 'Invalid parameters'}), 400

    conn = get_db_connection()
    try:
        user = conn.execute("SELECT id FROM users WHERE username = ?", (target_username,)).fetchone()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        conn.execute("UPDATE users SET role = ? WHERE username = ?", (new_role, target_username))
        conn.commit()
    finally:
        conn.close()

    return jsonify({'success': True, 'message': f'User {target_username} role changed to {new_role}'})
@admin_bp.route('/delete_user/<username>', methods=['POST'])
def admin_delete_user(username):
    if require_admin():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Invalid request'}), 400
    target_username = data.get('target_username')

    if not target_username or target_username == 'admin':
        return jsonify({'success': False, 'message': 'Cannot delete this user'}), 400

    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM waitlist WHERE username = ?", (target_username,))
        conn.execute("DELETE FROM notifications WHERE username = ?", (target_username,))
        conn.execute("DELETE FROM bookings WHERE username = ?", (target_username,))
        conn.execute("DELETE FROM users WHERE username = ?", (target_username,))
        conn.commit()
    finally:
        conn.close()

    return jsonify({'success': True, 'message': f'User {target_username} deleted'})
@admin_bp.route('/export_bookings/<username>')
def admin_export_bookings(username):
    if require_admin():
        return redirect(url_for('core.dashboard', username=username))
    conn = get_db_connection()
    try:
        bookings = conn.execute(
            "SELECT id, username, slot, vehicle, vehicle_plate, duration_hours, amount_paid, status, created_at "
            "FROM bookings ORDER BY created_at DESC"
        ).fetchall()
    finally:
        conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'User', 'Slot', 'Vehicle', 'Plate', 'Duration(h)', 'Amount(INR)', 'Status', 'Date'])
    for b in bookings:
        writer.writerow([b['id'], b['username'], b['slot'], b['vehicle'], b['vehicle_plate'] or '',
                         b['duration_hours'] or 1, b['amount_paid'] or 0, b['status'], b['created_at']])
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=all_bookings.csv'
    return response

@admin_bp.route('/api/stats/<username>')
def admin_api_stats(username):
    if require_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    conn = get_db_connection()
    try:
        stats = {
            'total_bookings': conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0],
            'active_bookings': conn.execute("SELECT COUNT(*) FROM bookings WHERE status='active'").fetchone()[0],
            'total_revenue': conn.execute("SELECT COALESCE(SUM(amount_paid),0) FROM bookings").fetchone()[0],
            'total_users': conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            'waitlist_count': conn.execute("SELECT COUNT(*) FROM waitlist").fetchone()[0],
        }
    finally:
        conn.close()
    return jsonify(stats)

@admin_bp.route('/waitlist/<username>')
def admin_waitlist(username):
    if require_admin():
        return redirect(url_for('core.dashboard', username=username))
    conn = get_db_connection()
    try:
        items = conn.execute(
            "SELECT w.*, u.email FROM waitlist w LEFT JOIN users u ON w.username = u.username ORDER BY w.created_at DESC"
        ).fetchall()
    finally:
        conn.close()
    return render_template('admin/admin_waitlist.html', username=username, waitlist=items)

@admin_bp.route('/waitlist/remove/<username>', methods=['POST'])
def admin_remove_waitlist(username):
    if require_admin():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Invalid request'}), 400
    wid = data.get('id')
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM waitlist WHERE id = ?", (wid,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'message': 'Removed from waitlist'})
