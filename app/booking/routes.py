import csv
import io
import logging
import os

from flask import Blueprint, jsonify, make_response, redirect, render_template, request, session, url_for
# Update all routes to use the new context manager
# This will be done systematically across all files

# First, let's fix the booking routes to use proper database connections
from ..core.database import (
    get_db_connection_legacy as get_db_connection, VEHICLE_RATES, add_notification, expire_old_bookings,
    sanitize_plate, get_peak_multiplier, get_loyalty_tier, PEAK_HOURS
)
from ..core.security import (
    sanitize_input, validate_vehicle_type, validate_duration, 
    validate_slot_id, validate_payment_method, validate_vehicle_plate,
    log_security_event
)
from ..core.email_utils import send_invoice_email
from ..core.routes import LOCATIONS, LOCATION_PREFIXES, TOTAL_SLOTS_PER_LOC
from .utils import generate_qr_base64, generate_pdf_ticket

logger = logging.getLogger(__name__)
booking_bp = Blueprint('booking', __name__)
def require_auth(username):
    return session.get('username') != username


@booking_bp.route('/book/<username>', methods=['GET', 'POST'])
def book(username):
    if require_auth(username):
        return redirect(url_for('auth.login'))
    expire_old_bookings()

    if request.method == 'POST':
        slot = request.form.get('slot', '').strip()
        vehicle = request.form.get('vehicle', '').strip()
        try:
            duration = int(request.form.get('duration', 1))
        except (ValueError, TypeError):
            duration = 0
        vehicle_plate = sanitize_plate(request.form.get('vehicle_plate', '').strip())
        start_time = request.form.get('start_time', '').strip()
        payment_method = request.form.get('payment_method', 'Cash').strip()
        if payment_method not in ('UPI', 'Card', 'Cash', 'Wallet'):
            payment_method = 'Cash'

        if not slot or vehicle not in VEHICLE_RATES or not (1 <= duration <= 24):
            return redirect(url_for('booking.book', username=username))

        multiplier = get_peak_multiplier()
        is_peak = multiplier > 1.0

        conn = get_db_connection()
        user = None
        try:
            existing = conn.execute(
                "SELECT id FROM bookings WHERE slot = ? AND status = 'active'", (slot,)
            ).fetchone()
            if existing:
                return redirect(url_for('booking.book', username=username, waitlist_slot=slot))

            user_row = conn.execute(
                "SELECT email, loyalty_points FROM users WHERE username = ?", (username,)
            ).fetchone()
            loyalty_pts = user_row['loyalty_points'] if user_row else 0
            tier = get_loyalty_tier(loyalty_pts)
            discount_pct = tier['discount']

            base_amount = VEHICLE_RATES.get(vehicle, 50) * duration
            peak_amount = round(base_amount * multiplier)
            loyalty_discount = round(peak_amount * discount_pct / 100)
            amount = peak_amount - loyalty_discount

            conn.execute(
                "INSERT INTO bookings (username, slot, vehicle, duration_hours, amount_paid, status, vehicle_plate, peak_booking, loyalty_discount, start_time, payment_method) "
                "VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)",
                (username, slot, vehicle, duration, amount, vehicle_plate, 1 if is_peak else 0, loyalty_discount, start_time or None, payment_method)
            )
            booking_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "UPDATE users SET favourite_slot = ?, loyalty_points = loyalty_points + ? WHERE username = ?",
                (slot, max(1, amount // 10), username)
            )
            conn.commit()
            user = user_row
        finally:
            conn.close()

        notif = f"\u2705 Booking confirmed: {slot} ({vehicle}) for {duration}h \u2014 \u20b9{amount}"
        if is_peak:
            notif += " (Peak pricing)"
        if loyalty_discount > 0:
            notif += f" | Loyalty discount: \u20b9{loyalty_discount}"
        add_notification(username, notif)

        if user and user['email']:
            booking_dict = {
                'id': booking_id, 'slot': slot, 'vehicle': vehicle,
                'vehicle_plate': vehicle_plate, 'duration_hours': duration,
                'amount_paid': amount, 'created_at': 'Just now',
                'peak_booking': 1 if is_peak else 0,
                'loyalty_discount': loyalty_discount,
                'payment_method': payment_method
            }
            # Send both confirmation and invoice emails
            from ..core.email_utils import send_booking_confirmation_email
            send_booking_confirmation_email(user['email'], username, booking_dict)
            send_invoice_email(user['email'], username, booking_dict)

        return redirect(url_for('booking.ticket', username=username, booking_id=booking_id))

    conn = get_db_connection()
    try:
        booked_slots = [r[0] for r in conn.execute(
            "SELECT slot FROM bookings WHERE status = 'active'"
        ).fetchall()]
        user_row = conn.execute(
            "SELECT favourite_slot, loyalty_points FROM users WHERE username = ?", (username,)
        ).fetchone()
    finally:
        conn.close()

    favourite_slot = user_row['favourite_slot'] if user_row else ''
    loyalty_pts = user_row['loyalty_points'] if user_row else 0
    tier = get_loyalty_tier(loyalty_pts)
    multiplier = get_peak_multiplier()
    is_peak = multiplier > 1.0
    locations = {
        loc: {
            'prefix': LOCATION_PREFIXES[loc],
            'available': TOTAL_SLOTS_PER_LOC - len([s for s in booked_slots if s.startswith(loc)])
        }
        for loc in LOCATIONS
    }
    waitlist_slot = request.args.get('waitlist_slot', '')
    return render_template('booking/booking.html', username=username, booked_slots=booked_slots,
                           locations=locations, vehicle_rates=VEHICLE_RATES,
                           favourite_slot=favourite_slot, waitlist_slot=waitlist_slot,
                           is_peak=is_peak, peak_multiplier=multiplier,
                           loyalty_tier=tier, peak_hours=PEAK_HOURS)


@booking_bp.route('/bookings/<username>')
def view_bookings(username):
    if require_auth(username):
        return redirect(url_for('auth.login'))

    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'all')

    conn = get_db_connection()
    try:
        query = "SELECT * FROM bookings WHERE username = ?"
        params = [username]
        if status_filter != 'all':
            query += " AND status = ?"
            params.append(status_filter)
        if search:
            query += " AND (slot LIKE ? OR vehicle LIKE ?)"
            params.extend([f'%{search}%', f'%{search}%'])
        query += " ORDER BY created_at DESC"
        bookings = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    return render_template('booking/view_bookings.html', bookings=bookings, username=username,
                           search=search, status_filter=status_filter,
                           vehicle_rates=VEHICLE_RATES)


@booking_bp.route('/ticket/<username>/<int:booking_id>')
def ticket(username, booking_id):
    if require_auth(username):
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    try:
        booking = conn.execute(
            "SELECT * FROM bookings WHERE id = ? AND username = ?", (booking_id, username)
        ).fetchone()
        existing_review = conn.execute(
            "SELECT rating, comment FROM reviews WHERE username = ? AND slot = ?",
            (username, booking['slot'] if booking else '')
        ).fetchone() if booking else None
    finally:
        conn.close()

    if booking:
        from datetime import datetime, timedelta
        start_time = booking['start_time'] or str(booking['created_at'])[:16]
        try:
            start_dt = datetime.strptime(start_time[:16], '%Y-%m-%dT%H:%M')
        except ValueError:
            try:
                start_dt = datetime.strptime(start_time[:16], '%Y-%m-%d %H:%M')
            except ValueError:
                start_dt = None
        end_time = None
        if start_dt:
            end_dt = start_dt + timedelta(hours=booking['duration_hours'] or 1)
            start_time = start_dt.strftime('%d %b %Y, %I:%M %p')
            end_time = end_dt.strftime('%d %b %Y, %I:%M %p')
        qr_data = (
            f"=== SMARTPARK TICKET ===\n"
            f"Ticket ID : #{booking['id']}\n"
            f"Customer  : {booking['username']}\n"
            f"Slot      : {booking['slot']}\n"
            f"Vehicle   : {booking['vehicle']}"
            + (f" ({booking['vehicle_plate']})" if booking['vehicle_plate'] else "") + "\n"
            f"Start     : {start_time}\n"
            f"End       : {end_time or 'N/A'}\n"
            f"Duration  : {booking['duration_hours'] or 1}h\n"
            f"Amount    : Rs.{int(booking['amount_paid'] or 0)}\n"
            f"Status    : {(booking['status'] or 'active').upper()}\n"
            f"======================="
        )
        qr_b64 = generate_qr_base64(qr_data)
        return render_template('booking/ticket.html', username=username, booking=booking,
                               vehicle_rates=VEHICLE_RATES, qr_b64=qr_b64,
                               existing_review=existing_review,
                               start_time=start_time, end_time=end_time)
    return redirect(url_for('core.dashboard', username=username))


@booking_bp.route('/cancel/<username>/<int:booking_id>', methods=['POST'])
def cancel_booking(username, booking_id):
    if require_auth(username):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    conn = get_db_connection()
    try:
        booking = conn.execute(
            "SELECT id, slot FROM bookings WHERE id = ? AND username = ? AND status = 'active'",
            (booking_id, username)
        ).fetchone()
        if not booking:
            return jsonify({'success': False, 'message': 'Booking not found or already cancelled'})
        conn.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
        conn.commit()
        slot = booking['slot']
    finally:
        conn.close()

    add_notification(username, f"\u274c Booking #{booking_id} for slot {slot} has been cancelled.")
    return jsonify({'success': True, 'message': 'Booking cancelled successfully'})


@booking_bp.route('/slots/<username>')
def slot_management(username):
    if require_auth(username):
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    try:
        if session.get('role') == 'admin':
            bookings = conn.execute(
                "SELECT * FROM bookings WHERE status = 'active' ORDER BY created_at DESC"
            ).fetchall()
        else:
            bookings = conn.execute(
                "SELECT * FROM bookings WHERE username = ? AND status = 'active' ORDER BY created_at DESC",
                (username,)
            ).fetchall()
    finally:
        conn.close()

    return render_template('booking/slot_management.html', username=username, bookings=bookings)


@booking_bp.route('/release_slot/<username>', methods=['POST'])
def release_slot(username):
    if require_auth(username):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Invalid request'}), 400
    slot_to_release = data.get('slot')
    if not slot_to_release:
        return jsonify({'success': False, 'message': 'No slot specified'}), 400

    conn = get_db_connection()
    try:
        if session.get('role') == 'admin':
            booking = conn.execute(
                "SELECT id FROM bookings WHERE slot = ? AND status = 'active'", (slot_to_release,)
            ).fetchone()
        else:
            booking = conn.execute(
                "SELECT id FROM bookings WHERE slot = ? AND username = ? AND status = 'active'",
                (slot_to_release, username)
            ).fetchone()

        if not booking:
            return jsonify({'success': False, 'message': 'Slot not found or not authorized'}), 404

        if session.get('role') == 'admin':
            conn.execute("UPDATE bookings SET status = 'completed' WHERE slot = ? AND status = 'active'", (slot_to_release,))
        else:
            conn.execute("UPDATE bookings SET status = 'completed' WHERE slot = ? AND username = ? AND status = 'active'",
                         (slot_to_release, username))
        conn.commit()
    finally:
        conn.close()

    return jsonify({'success': True, 'message': f'Slot {slot_to_release} released successfully'})


@booking_bp.route('/extend/<username>/<int:booking_id>', methods=['POST'])
def extend_booking(username, booking_id):
    if require_auth(username):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Invalid request'}), 400
    try:
        extra_hours = int(data.get('extra_hours', 1))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid hours'}), 400
    if extra_hours < 1:
        return jsonify({'success': False, 'message': 'Invalid hours'})
    conn = get_db_connection()
    try:
        booking = conn.execute(
            "SELECT id, slot, vehicle, duration_hours, amount_paid FROM bookings "
            "WHERE id = ? AND username = ? AND status = 'active'",
            (booking_id, username)
        ).fetchone()
        if not booking:
            return jsonify({'success': False, 'message': 'Active booking not found'})
        extra_cost = VEHICLE_RATES.get(booking['vehicle'], 50) * extra_hours
        new_duration = booking['duration_hours'] + extra_hours
        new_amount = booking['amount_paid'] + extra_cost
        conn.execute(
            "UPDATE bookings SET duration_hours = ?, amount_paid = ? WHERE id = ?",
            (new_duration, new_amount, booking_id)
        )
        conn.commit()
    finally:
        conn.close()
    add_notification(username, f"\u23f1\ufe0f Booking #{booking_id} extended by {extra_hours}h. New total: {new_duration}h \u2014 \u20b9{new_amount}")
    return jsonify({'success': True, 'message': f'Extended by {extra_hours}h. New total: {new_duration}h (\u20b9{new_amount})',
                    'new_duration': new_duration, 'new_amount': new_amount})


@booking_bp.route('/api/rates')
def api_rates():
    multiplier = get_peak_multiplier()
    return jsonify({v: round(r * multiplier) for v, r in VEHICLE_RATES.items()})


@booking_bp.route('/api/pricing')
def api_pricing():
    multiplier = get_peak_multiplier()
    return jsonify({
        'is_peak': multiplier > 1.0,
        'multiplier': multiplier,
        'peak_hours': PEAK_HOURS,
        'rates': {v: round(r * multiplier) for v, r in VEHICLE_RATES.items()},
        'base_rates': VEHICLE_RATES
    })


@booking_bp.route('/waitlist/<username>', methods=['POST'])
def join_waitlist(username):
    if require_auth(username):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Invalid request'}), 400
    slot = data.get('slot', '').strip()
    vehicle = data.get('vehicle', '').strip()
    try:
        duration = max(1, int(data.get('duration', 1)))
    except (ValueError, TypeError):
        duration = 1
    vehicle_plate = data.get('vehicle_plate', '').strip().upper()
    if not slot or not vehicle:
        return jsonify({'success': False, 'message': 'Slot and vehicle required'})
    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM waitlist WHERE username = ? AND slot = ?", (username, slot)
        ).fetchone()
        if existing:
            return jsonify({'success': False, 'message': 'Already on waitlist for this slot'})
        conn.execute(
            "INSERT INTO waitlist (username, slot, vehicle, duration_hours, vehicle_plate) VALUES (?, ?, ?, ?, ?)",
            (username, slot, vehicle, duration, vehicle_plate)
        )
        conn.commit()
    finally:
        conn.close()
    add_notification(username, f"\u23f3 Added to waitlist for slot {slot}. You'll be notified when it's free.")
    return jsonify({'success': True, 'message': f'Added to waitlist for {slot}'})


@booking_bp.route('/waitlist/<username>', methods=['GET'])
def view_waitlist(username):
    if require_auth(username):
        return redirect(url_for('auth.login'))
    conn = get_db_connection()
    try:
        items = conn.execute(
            "SELECT * FROM waitlist WHERE username = ? ORDER BY created_at DESC", (username,)
        ).fetchall()
    finally:
        conn.close()
    return jsonify([dict(i) for i in items])


@booking_bp.route('/waitlist/cancel/<username>/<int:waitlist_id>', methods=['POST'])
def cancel_waitlist(username, waitlist_id):
    if require_auth(username):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM waitlist WHERE id = ? AND username = ?", (waitlist_id, username))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'message': 'Removed from waitlist'})


@booking_bp.route('/export/<username>')
def export_bookings(username):
    if require_auth(username):
        return redirect(url_for('auth.login'))
    conn = get_db_connection()
    try:
        bookings = conn.execute(
            "SELECT id, slot, vehicle, vehicle_plate, duration_hours, amount_paid, status, created_at "
            "FROM bookings WHERE username = ? ORDER BY created_at DESC",
            (username,)
        ).fetchall()
    finally:
        conn.close()
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(['ID', 'Slot', 'Vehicle', 'Plate', 'Duration(h)', 'Amount(INR)', 'Status', 'Date'])
    for b in bookings:
        writer.writerow([b['id'], b['slot'], b['vehicle'], b['vehicle_plate'] or '',
                         b['duration_hours'] or 1, b['amount_paid'] or 0, b['status'], b['created_at']])
    response = make_response(output.getvalue().encode('utf-8'))
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=bookings_{username}.csv'
    return response


@booking_bp.route('/api/expire', methods=['POST'])
def trigger_expire():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    count = expire_old_bookings()
    return jsonify({'success': True, 'expired': count, 'message': f'{count} booking(s) expired'})


@booking_bp.route('/email_invoice/<username>/<int:booking_id>', methods=['POST'])
def email_invoice(username, booking_id):
    if require_auth(username):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    conn = get_db_connection()
    try:
        booking = conn.execute(
            "SELECT * FROM bookings WHERE id = ? AND username = ?", (booking_id, username)
        ).fetchone()
        user = conn.execute(
            "SELECT email FROM users WHERE username = ?", (username,)
        ).fetchone()
    finally:
        conn.close()
    if not booking or not user or not user['email']:
        return jsonify({'success': False, 'message': 'No email address found for this account'})
    from ..core.email_utils import send_invoice_email
    send_invoice_email(user['email'], username, dict(zip(booking.keys(), tuple(booking))))
    return jsonify({'success': True, 'message': f'Invoice sent to {user["email"]}'})


@booking_bp.route('/pdf/<username>/<int:booking_id>')
def download_pdf(username, booking_id):
    if require_auth(username):
        return redirect(url_for('auth.login'))
    conn = get_db_connection()
    try:
        booking = conn.execute(
            "SELECT * FROM bookings WHERE id = ? AND username = ?", (booking_id, username)
        ).fetchone()
    finally:
        conn.close()
    if not booking:
        return redirect(url_for('core.dashboard', username=username))
    pdf_bytes = generate_pdf_ticket(booking)
    if not pdf_bytes:
        return jsonify({'error': 'PDF generation failed'}), 500
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=ticket_{booking_id}.pdf'
    return response


@booking_bp.route('/review/<username>', methods=['POST'])
def submit_review(username):
    if require_auth(username):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Invalid request'}), 400
    slot = data.get('slot', '').strip()
    try:
        rating = int(data.get('rating', 0))
    except (ValueError, TypeError):
        rating = 0
    comment = data.get('comment', '').strip()[:500]
    if not slot or not (1 <= rating <= 5):
        return jsonify({'success': False, 'message': 'Slot and rating (1-5) required'})
    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM reviews WHERE username = ? AND slot = ?", (username, slot)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE reviews SET rating = ?, comment = ? WHERE username = ? AND slot = ?",
                (rating, comment, username, slot)
            )
        else:
            conn.execute(
                "INSERT INTO reviews (username, slot, rating, comment) VALUES (?, ?, ?, ?)",
                (username, slot, rating, comment)
            )
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'message': 'Review submitted!'})


@booking_bp.route('/api/reviews/<slot>')
def slot_reviews(slot):
    conn = get_db_connection()
    try:
        reviews = conn.execute(
            "SELECT username, rating, comment, created_at FROM reviews WHERE slot = ? ORDER BY created_at DESC LIMIT 10",
            (slot,)
        ).fetchall()
        avg = conn.execute(
            "SELECT AVG(rating) FROM reviews WHERE slot = ?", (slot,)
        ).fetchone()[0]
    finally:
        conn.close()
    return jsonify({'reviews': [dict(r) for r in reviews], 'avg_rating': round(avg, 1) if avg else None})


@booking_bp.route('/favourite/<username>', methods=['POST'])
def set_favourite(username):
    if require_auth(username):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Invalid request'}), 400
    slot = data.get('slot', '').strip()
    conn = get_db_connection()
    try:
        conn.execute("UPDATE users SET favourite_slot = ? WHERE username = ?", (slot, username))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'message': f'Favourite slot set to {slot}' if slot else 'Favourite slot cleared'})

@booking_bp.route('/email/test/<username>', methods=['POST'])
def test_email(username):
    """Test email functionality"""
    if require_auth(username):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT email FROM users WHERE username = ?", (username,)
        ).fetchone()
    finally:
        conn.close()
    
    if not user or not user['email']:
        return jsonify({'success': False, 'message': 'No email address found for this account'})
    
    from ..core.email_utils import send_test_email
    success = send_test_email(user['email'], username)
    
    if success:
        return jsonify({'success': True, 'message': f'Test email sent to {user["email"]}'})
    else:
        return jsonify({'success': False, 'message': 'Failed to send test email'})


@booking_bp.route('/email/resend_invoice/<username>/<int:booking_id>', methods=['POST'])
def resend_invoice(username, booking_id):
    """Resend invoice email for a specific booking"""
    if require_auth(username):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    try:
        booking = conn.execute(
            "SELECT * FROM bookings WHERE id = ? AND username = ?", (booking_id, username)
        ).fetchone()
        user = conn.execute(
            "SELECT email FROM users WHERE username = ?", (username,)
        ).fetchone()
    finally:
        conn.close()
    
    if not booking:
        return jsonify({'success': False, 'message': 'Booking not found'})
    
    if not user or not user['email']:
        return jsonify({'success': False, 'message': 'No email address found for this account'})
    
    from ..core.email_utils import send_invoice_email
    booking_dict = dict(zip(booking.keys(), tuple(booking)))
    success = send_invoice_email(user['email'], username, booking_dict)
    
    if success:
        add_notification(username, f"📧 Invoice for booking #{booking_id} has been resent to {user['email']}")
        return jsonify({'success': True, 'message': f'Invoice resent to {user["email"]}'})
    else:
        return jsonify({'success': False, 'message': 'Failed to send invoice email'})


@booking_bp.route('/email/monthly_summary/<username>', methods=['POST'])
def send_monthly_summary(username):
    """Send monthly summary email"""
    if require_auth(username):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT email, loyalty_points, favourite_slot FROM users WHERE username = ?", (username,)
        ).fetchone()
        
        # Get monthly stats
        from datetime import datetime, timedelta
        current_month = datetime.now().replace(day=1)
        next_month = (current_month + timedelta(days=32)).replace(day=1)
        
        bookings = conn.execute(
            "SELECT COUNT(*) as count, SUM(amount_paid) as total, SUM(duration_hours) as hours "
            "FROM bookings WHERE username = ? AND created_at >= ? AND created_at < ?",
            (username, current_month.strftime('%Y-%m-%d'), next_month.strftime('%Y-%m-%d'))
        ).fetchone()
        
    finally:
        conn.close()
    
    if not user or not user['email']:
        return jsonify({'success': False, 'message': 'No email address found for this account'})
    
    summary_data = {
        'total_bookings': bookings['count'] or 0,
        'total_spent': int(bookings['total'] or 0),
        'total_hours': int(bookings['hours'] or 0),
        'favorite_slot': user['favourite_slot'] or 'N/A',
        'loyalty_points': user['loyalty_points'] or 0,
        'month_year': datetime.now().strftime('%B %Y')
    }
    
    from ..core.email_utils import send_monthly_summary_email
    success = send_monthly_summary_email(user['email'], username, summary_data)
    
    if success:
        return jsonify({'success': True, 'message': f'Monthly summary sent to {user["email"]}'})
    else:
        return jsonify({'success': False, 'message': 'Failed to send monthly summary'})


@booking_bp.route('/email/reminder/<username>/<int:booking_id>', methods=['POST'])
def send_reminder(username, booking_id):
    """Send booking reminder email"""
    if require_auth(username):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json() or {}
    reminder_type = data.get('type', 'upcoming')  # upcoming, expiring_soon, expired
    
    conn = get_db_connection()
    try:
        booking = conn.execute(
            "SELECT * FROM bookings WHERE id = ? AND username = ?", (booking_id, username)
        ).fetchone()
        user = conn.execute(
            "SELECT email FROM users WHERE username = ?", (username,)
        ).fetchone()
    finally:
        conn.close()
    
    if not booking:
        return jsonify({'success': False, 'message': 'Booking not found'})
    
    if not user or not user['email']:
        return jsonify({'success': False, 'message': 'No email address found for this account'})
    
    from ..core.email_utils import send_booking_reminder_email
    booking_dict = dict(zip(booking.keys(), tuple(booking)))
    success = send_booking_reminder_email(user['email'], username, booking_dict, reminder_type)
    
    if success:
        return jsonify({'success': True, 'message': f'Reminder sent to {user["email"]}'})
    else:
        return jsonify({'success': False, 'message': 'Failed to send reminder'})

@booking_bp.route('/email_manager/<username>')
def email_manager(username):
    """Email management interface"""
    if require_auth(username):
        return redirect(url_for('auth.login'))
    
    # Get SMTP configuration for display
    smtp_config = {
        'smtp_host': os.environ.get('SMTP_HOST', 'smtp.gmail.com'),
        'smtp_port': os.environ.get('SMTP_PORT', '587'),
        'smtp_user': os.environ.get('SMTP_USER', 'Not configured')
    }
    
    return render_template('booking/email_management.html', 
                         username=username, 
                         **smtp_config)