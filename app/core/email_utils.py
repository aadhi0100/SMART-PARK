import logging
import os
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import json

logger = logging.getLogger(__name__)
FROM_NAME = 'SmartPark'
MAX_RETRIES = 3
RETRY_DELAY = 2


def _send(to_email: str, subject: str, html: str, attachments: list = None):
    """Enhanced email sending with retry logic and attachment support"""
    smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', 587))
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASS', '')

    if not smtp_user or not smtp_pass:
        logger.error('[Email] SMTP_USER or SMTP_PASS not configured')
        return False
    if not to_email or '@' not in to_email:
        logger.error('[Email] Invalid recipient email address: %s', to_email)
        return False
    
    # Special handling for Render deployment
    is_render = os.environ.get('RENDER') or os.environ.get('RENDER_SERVICE_ID')
    
    for attempt in range(MAX_RETRIES):
        try:
            logger.info('[Email] Attempt %d: Sending "%s" to %s via %s:%s', 
                       attempt + 1, subject, to_email, smtp_host, smtp_port)
            
            msg = MIMEMultipart('mixed')
            msg['Subject'] = subject
            msg['From'] = f'{FROM_NAME} <{smtp_user}>'
            msg['To'] = to_email
            msg['X-Priority'] = '1'  # High priority
            
            # Add HTML content
            msg.attach(MIMEText(html, 'html', 'utf-8'))
            
            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    if isinstance(attachment, dict) and 'data' in attachment and 'filename' in attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment['data'])
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename= {attachment["filename"]}'
                        )
                        msg.attach(part)
            
            # Use longer timeout for Render
            timeout = 60 if is_render else 30
            
            with smtplib.SMTP(smtp_host, smtp_port, timeout=timeout) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, to_email, msg.as_string())
            
            logger.info('[Email] Successfully sent "%s" to %s', subject, to_email)
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error('[Email] Authentication failed — check SMTP_USER/SMTP_PASS: %s', e)
            break  # Don't retry auth errors
        except smtplib.SMTPRecipientsRefused as e:
            logger.error('[Email] Recipient refused %s: %s', to_email, e)
            break  # Don't retry recipient errors
        except (smtplib.SMTPException, OSError) as e:
            logger.warning('[Email] Attempt %d failed to send to %s: %s', attempt + 1, to_email, e)
            if attempt < MAX_RETRIES - 1:
                import time
                delay = RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                logger.info('[Email] Retrying in %d seconds...', delay)
                time.sleep(delay)
            else:
                logger.error('[Email] All attempts failed to send to %s', to_email)
    
    return False


def _send_async(to_email: str, subject: str, html: str, attachments: list = None):
    """Send email in a background thread so it never blocks the request."""
    t = threading.Thread(
        target=_send, 
        args=(to_email, subject, html, attachments), 
        daemon=True
    )
    t.start()
    return t


def send_bulk_emails(recipients: list, subject: str, html_template: str, personalization_data: dict = None):
    """Send bulk emails with personalization"""
    threads = []
    for recipient in recipients:
        if isinstance(recipient, dict):
            email = recipient.get('email')
            name = recipient.get('name', 'Customer')
        else:
            email = recipient
            name = 'Customer'
        
        if email and '@' in email:
            # Personalize the HTML
            personalized_html = html_template.replace('{{name}}', name)
            if personalization_data:
                for key, value in personalization_data.items():
                    personalized_html = personalized_html.replace(f'{{{{{key}}}}}', str(value))
            
            thread = _send_async(email, subject, personalized_html)
            threads.append(thread)
    
    return threads


def send_welcome_email(to_email: str, username: str):
    base_url = os.environ.get('APP_BASE_URL', 'https://smart-park-z1yb.onrender.com')
    html = (
        '<div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;background:#f8fafc;border-radius:12px;overflow:hidden">'
        '<div style="background:linear-gradient(135deg,#2563eb,#4f46e5);padding:40px 32px;text-align:center">'
        '<h1 style="color:#fff;margin:0;font-size:28px">SmartPark</h1>'
        '<p style="color:#bfdbfe;margin:8px 0 0">Intelligent Parking Management</p>'
        '</div>'
        '<div style="padding:32px">'
        f'<h2 style="color:#1e293b">Welcome, {username}!</h2>'
        '<p style="color:#475569;line-height:1.6">Your SmartPark account has been created successfully. '
        'You can now book parking slots, track your bookings, and enjoy loyalty rewards.</p>'
        f'<a href="{base_url}/auth/login" style="display:inline-block;background:#2563eb;color:#fff;'
        'padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;margin-top:8px">'
        'Login to SmartPark</a>'
        '</div>'
        '<div style="background:#f1f5f9;padding:16px 32px;text-align:center">'
        '<p style="color:#94a3b8;font-size:12px;margin:0">© 2024 SmartPark. All rights reserved.</p>'
        '</div></div>'
    )
    _send_async(to_email, f'Welcome to SmartPark, {username}!', html)


def send_invoice_email(to_email: str, username: str, booking: dict):
    """Enhanced invoice email with better formatting and QR code"""
    base_url = os.environ.get('APP_BASE_URL', 'https://smart-park-z1yb.onrender.com')
    from ..booking.utils import generate_qr_base64

    # Extract booking details with better error handling
    bid = booking.get('id', 0)
    slot = booking.get('slot', 'N/A')
    vehicle = booking.get('vehicle', 'N/A')
    plate = booking.get('vehicle_plate', '') or ''
    duration = max(1, booking.get('duration_hours', 1) or 1)
    amount_paid = max(0, int(booking.get('amount_paid', 0) or 0))
    loyalty_disc = max(0, int(booking.get('loyalty_discount', 0) or 0))
    is_peak = bool(booking.get('peak_booking', False))
    status = (booking.get('status') or 'active').upper()
    payment_method = booking.get('payment_method', 'Cash')
    
    # Format dates properly
    created_at = booking.get('created_at', '')
    if isinstance(created_at, str) and len(created_at) >= 10:
        try:
            date_obj = datetime.strptime(created_at[:19], '%Y-%m-%d %H:%M:%S')
            formatted_date = date_obj.strftime('%d %b %Y, %I:%M %p')
            invoice_date = date_obj.strftime('%d %b %Y')
        except ValueError:
            formatted_date = created_at[:16]
            invoice_date = created_at[:10]
    else:
        formatted_date = 'Just now'
        invoice_date = datetime.now().strftime('%d %b %Y')
    
    # Calculate pricing breakdown
    multiplier = 1.5 if is_peak else 1.0
    base_amount = round((amount_paid + loyalty_disc) / multiplier) if multiplier > 0 else amount_paid
    peak_surcharge = round(base_amount * (multiplier - 1)) if is_peak else 0
    vehicle_rate = round(base_amount / duration) if duration > 0 else 0

    # Generate QR code with comprehensive data
    qr_data = (
        f"=== SMARTPARK INVOICE ===\n"
        f"Invoice #: {bid:05d}\n"
        f"Date: {invoice_date}\n"
        f"Customer: {username}\n"
        f"Slot: {slot}\n"
        f"Vehicle: {vehicle}" + (f" ({plate})" if plate else "") + "\n"
        f"Duration: {duration}h\n"
        f"Amount: ₹{amount_paid}\n"
        f"Payment: {payment_method}\n"
        f"Status: {status}\n"
        f"========================"
    )
    
    qr_b64 = generate_qr_base64(qr_data)
    qr_img_tag = (
        f'<img src="data:image/png;base64,{qr_b64}" alt="Invoice QR Code" '
        f'style="width:180px;height:180px;display:block;margin:0 auto;border:2px solid #e5e7eb;border-radius:8px;padding:8px;background:white"/>'
        if qr_b64 else '<div style="width:180px;height:180px;background:#f3f4f6;border:2px dashed #d1d5db;border-radius:8px;display:flex;align-items:center;justify-content:center;margin:0 auto;"><span style="color:#9ca3af;font-size:12px;">QR Code Unavailable</span></div>'
    )

    # Build pricing rows
    peak_row = (
        f'<tr><td style="padding:8px 16px;border-bottom:1px solid #e5e7eb;color:#dc2626;">Peak Hour Surcharge (1.5×)</td>'
        f'<td style="padding:8px 16px;text-align:center;border-bottom:1px solid #e5e7eb;">—</td>'
        f'<td style="padding:8px 16px;text-align:right;border-bottom:1px solid #e5e7eb;">—</td>'
        f'<td style="padding:8px 16px;text-align:right;font-weight:600;border-bottom:1px solid #e5e7eb;color:#dc2626;">+₹{peak_surcharge}</td></tr>'
    ) if is_peak and peak_surcharge > 0 else ''
    
    loyalty_row = (
        f'<tr style="background:#f0fdf4;"><td style="padding:8px 16px;border-bottom:1px solid #e5e7eb;color:#059669;">Loyalty Discount ({get_loyalty_tier_name(loyalty_disc)})</td>'
        f'<td style="padding:8px 16px;text-align:center;border-bottom:1px solid #e5e7eb;">—</td>'
        f'<td style="padding:8px 16px;text-align:right;border-bottom:1px solid #e5e7eb;">—</td>'
        f'<td style="padding:8px 16px;text-align:right;font-weight:600;color:#059669;border-bottom:1px solid #e5e7eb;">-₹{loyalty_disc}</td></tr>'
    ) if loyalty_disc > 0 else ''

    # Enhanced professional invoice template
    html = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SmartPark Invoice #{bid:05d}</title>
</head>
<body style="margin:0;padding:20px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f8fafc;">
<div style="max-width:650px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1);">
  
  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1e40af 0%,#3b82f6 100%);color:white;padding:32px 40px;position:relative;">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;">
      <div>
        <h1 style="margin:0;font-size:32px;font-weight:700;letter-spacing:-0.5px;">SmartPark</h1>
        <p style="margin:4px 0 0;font-size:14px;opacity:0.9;">Professional Parking Solutions</p>
        <div style="margin-top:16px;">
          <span style="background:rgba(255,255,255,0.2);padding:4px 12px;border-radius:20px;font-size:12px;font-weight:500;">INVOICE</span>
        </div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:12px;opacity:0.8;margin-bottom:4px;">Invoice Number</div>
        <div style="font-size:28px;font-weight:700;line-height:1;">#{bid:05d}</div>
        <div style="font-size:12px;opacity:0.8;margin-top:8px;">{invoice_date}</div>
      </div>
    </div>
  </div>
  
  <!-- Customer & Booking Info -->
  <div style="padding:32px 40px;border-bottom:1px solid #e5e7eb;">
    <div style="display:flex;justify-content:space-between;gap:40px;">
      <div style="flex:1;">
        <h3 style="margin:0 0 12px;font-size:14px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Bill To</h3>
        <div style="font-size:18px;font-weight:600;color:#111827;margin-bottom:4px;">{username}</div>
        <div style="font-size:14px;color:#6b7280;">{vehicle}{f" • {plate}" if plate else ""}</div>
        <div style="margin-top:12px;font-size:12px;color:#9ca3af;">Customer ID: {username.upper()}</div>
      </div>
      <div style="flex:1;text-align:right;">
        <h3 style="margin:0 0 12px;font-size:14px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Booking Details</h3>
        <div style="font-size:14px;color:#374151;line-height:1.6;">
          <div style="margin-bottom:6px;"><strong>Slot:</strong> <span style="color:#1e40af;font-weight:600;">{slot}</span></div>
          <div style="margin-bottom:6px;"><strong>Duration:</strong> {duration} hour{"s" if duration != 1 else ""}</div>
          <div style="margin-bottom:6px;"><strong>Status:</strong> <span style="color:#059669;font-weight:600;">{status}</span></div>
          <div style="margin-bottom:6px;"><strong>Payment:</strong> {payment_method}</div>
          <div><strong>Booked:</strong> {formatted_date}</div>
        </div>
      </div>
    </div>
  </div>
  
  <!-- Invoice Table -->
  <div style="overflow-x:auto;">
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <thead>
        <tr style="background:#f8fafc;">
          <th style="padding:16px;text-align:left;font-weight:600;color:#374151;border-bottom:2px solid #e5e7eb;">Description</th>
          <th style="padding:16px;text-align:center;font-weight:600;color:#374151;border-bottom:2px solid #e5e7eb;width:80px;">Qty</th>
          <th style="padding:16px;text-align:right;font-weight:600;color:#374151;border-bottom:2px solid #e5e7eb;width:100px;">Rate</th>
          <th style="padding:16px;text-align:right;font-weight:600;color:#374151;border-bottom:2px solid #e5e7eb;width:100px;">Amount</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style="padding:12px 16px;border-bottom:1px solid #e5e7eb;">Parking Service - {vehicle} at {slot}</td>
          <td style="padding:12px 16px;text-align:center;border-bottom:1px solid #e5e7eb;">{duration}h</td>
          <td style="padding:12px 16px;text-align:right;border-bottom:1px solid #e5e7eb;">₹{vehicle_rate}/hr</td>
          <td style="padding:12px 16px;text-align:right;font-weight:600;border-bottom:1px solid #e5e7eb;">₹{base_amount}</td>
        </tr>
        {peak_row}
        {loyalty_row}
      </tbody>
      <tfoot>
        <tr style="background:linear-gradient(135deg,#1e40af 0%,#3b82f6 100%);color:white;">
          <td colspan="3" style="padding:16px;font-weight:700;font-size:16px;">TOTAL AMOUNT PAID</td>
          <td style="padding:16px;text-align:right;font-weight:700;font-size:18px;">₹{amount_paid}</td>
        </tr>
      </tfoot>
    </table>
  </div>
  
  <!-- Payment Status -->
  <div style="padding:20px 40px;background:#f0fdf4;border-top:1px solid #e5e7eb;">
    <div style="display:flex;align-items:center;gap:8px;">
      <span style="color:#059669;font-size:18px;">✓</span>
      <span style="color:#059669;font-weight:600;font-size:14px;">Payment Received Successfully</span>
      <span style="color:#6b7280;font-size:12px;margin-left:auto;">via {payment_method}</span>
    </div>
  </div>
  
  <!-- QR Code Section -->
  <div style="padding:32px 40px;text-align:center;background:#fafbfc;">
    <h3 style="margin:0 0 16px;font-size:16px;color:#374151;font-weight:600;">Digital Receipt</h3>
    <p style="margin:0 0 20px;font-size:13px;color:#6b7280;line-height:1.5;">Scan this QR code for quick access to your booking details</p>
    {qr_img_tag}
    <p style="margin:16px 0 0;font-size:11px;color:#9ca3af;">Contains complete invoice and booking information</p>
  </div>
  
  <!-- Action Buttons -->
  <div style="padding:24px 40px;border-top:1px solid #e5e7eb;">
    <div style="text-align:center;">
      <a href="{base_url}/booking/bookings/{username}" 
         style="display:inline-block;background:linear-gradient(135deg,#1e40af 0%,#3b82f6 100%);color:white;padding:12px 32px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;margin-right:16px;box-shadow:0 2px 4px rgba(59,130,246,0.3);">View All Bookings</a>
      <a href="{base_url}/booking/ticket/{username}/{bid}" 
         style="display:inline-block;background:white;color:#1e40af;padding:12px 32px;border:2px solid #1e40af;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">View Ticket</a>
    </div>
  </div>
  
  <!-- Footer -->
  <div style="background:#111827;color:white;text-align:center;padding:24px 40px;">
    <div style="font-size:14px;font-weight:600;margin-bottom:8px;">SmartPark - Intelligent Parking Solutions</div>
    <div style="font-size:12px;opacity:0.8;line-height:1.5;">
      Present this invoice at parking entrance | 24/7 Customer Support<br>
      Email: support@smartpark.com | Web: www.smartpark.com
    </div>
    <div style="margin-top:16px;font-size:10px;opacity:0.6;">
      © 2024 SmartPark. All rights reserved. | Invoice generated on {datetime.now().strftime('%d %b %Y at %I:%M %p')}
    </div>
  </div>
  
</div>
</body>
</html>
    '''
    
    success = _send_async(to_email, f'SmartPark Invoice #{bid:05d} - ₹{amount_paid} Paid', html)
    
    # Log the email sending attempt
    logger.info('[Invoice] Sent invoice #%d to %s (Amount: ₹%d)', bid, to_email, amount_paid)
    
    return success is not None


def get_loyalty_tier_name(discount_amount: int) -> str:
    """Get loyalty tier name based on discount amount"""
    if discount_amount >= 15:
        return "Platinum"
    elif discount_amount >= 10:
        return "Gold"
    elif discount_amount >= 5:
        return "Silver"
    else:
        return "Bronze"


def send_booking_confirmation_email(to_email: str, username: str, booking: dict):
    """Send immediate booking confirmation with parking instructions"""
    base_url = os.environ.get('APP_BASE_URL', 'https://smart-park-z1yb.onrender.com')
    
    slot = booking.get('slot', 'N/A')
    vehicle = booking.get('vehicle', 'N/A')
    duration = booking.get('duration_hours', 1)
    amount = booking.get('amount_paid', 0)
    booking_id = booking.get('id', 0)
    
    html = f'''
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Booking Confirmed</title></head>
<body style="margin:0;padding:20px;font-family:Arial,sans-serif;background:#f8fafc;">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 6px rgba(0,0,0,0.1);">
  <div style="background:linear-gradient(135deg,#10b981,#059669);color:white;padding:32px;text-align:center;">
    <div style="font-size:48px;margin-bottom:16px;">✓</div>
    <h1 style="margin:0;font-size:28px;font-weight:700;">Booking Confirmed!</h1>
    <p style="margin:8px 0 0;font-size:16px;opacity:0.9;">Your parking slot is reserved</p>
  </div>
  
  <div style="padding:32px;">
    <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:24px;margin-bottom:24px;">
      <h2 style="margin:0 0 16px;color:#065f46;font-size:18px;">Booking Details</h2>
      <div style="display:grid;gap:12px;">
        <div><strong>Slot:</strong> <span style="color:#059669;font-weight:600;">{slot}</span></div>
        <div><strong>Vehicle:</strong> {vehicle}</div>
        <div><strong>Duration:</strong> {duration} hour{"s" if duration != 1 else ""}</div>
        <div><strong>Amount Paid:</strong> <span style="color:#059669;font-weight:600;">₹{amount}</span></div>
        <div><strong>Booking ID:</strong> #{booking_id}</div>
      </div>
    </div>
    
    <div style="background:#fef3c7;border:1px solid #fbbf24;border-radius:8px;padding:20px;margin-bottom:24px;">
      <h3 style="margin:0 0 12px;color:#92400e;font-size:16px;">Important Instructions</h3>
      <ul style="margin:0;padding-left:20px;color:#92400e;line-height:1.6;">
        <li>Arrive within 15 minutes of your booking time</li>
        <li>Keep this email handy for entry verification</li>
        <li>Your slot will be held for the full duration</li>
        <li>Contact support if you need to extend or cancel</li>
      </ul>
    </div>
    
    <div style="text-align:center;">
      <a href="{base_url}/booking/ticket/{username}/{booking_id}" 
         style="display:inline-block;background:#059669;color:white;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:600;margin-right:12px;">View Ticket</a>
      <a href="{base_url}/booking/bookings/{username}" 
         style="display:inline-block;background:white;color:#059669;border:2px solid #059669;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;">My Bookings</a>
    </div>
  </div>
  
  <div style="background:#f9fafb;padding:20px;text-align:center;color:#6b7280;font-size:12px;">
    Need help? Contact us at support@smartpark.com or call +91-XXXX-XXXX
  </div>
</div>
</body>
</html>
    '''
    
    return _send_async(to_email, f'✓ Booking Confirmed - Slot {slot} Reserved', html)


def send_booking_reminder_email(to_email: str, username: str, booking: dict, reminder_type: str = 'upcoming'):
    """Send booking reminders (upcoming expiry, expired, etc.)"""
    base_url = os.environ.get('APP_BASE_URL', 'https://smart-park-z1yb.onrender.com')
    
    slot = booking.get('slot', 'N/A')
    booking_id = booking.get('id', 0)
    
    if reminder_type == 'expiring_soon':
        subject = f'⏰ Parking Expires Soon - Slot {slot}'
        header_color = '#f59e0b'
        icon = '⏰'
        title = 'Parking Expires Soon'
        message = 'Your parking session will expire in 30 minutes. You can extend it if needed.'
        cta_text = 'Extend Booking'
        cta_url = f'{base_url}/booking/ticket/{username}/{booking_id}'
    elif reminder_type == 'expired':
        subject = f'❌ Parking Expired - Slot {slot}'
        header_color = '#dc2626'
        icon = '❌'
        title = 'Parking Session Expired'
        message = 'Your parking session has ended. Please move your vehicle to avoid additional charges.'
        cta_text = 'View Details'
        cta_url = f'{base_url}/booking/bookings/{username}'
    else:  # upcoming
        subject = f'🅿️ Upcoming Parking - Slot {slot}'
        header_color = '#3b82f6'
        icon = '🅿️'
        title = 'Parking Reminder'
        message = 'Your parking session starts in 1 hour. Make sure to arrive on time.'
        cta_text = 'View Ticket'
        cta_url = f'{base_url}/booking/ticket/{username}/{booking_id}'
    
    html = f'''
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Parking Reminder</title></head>
<body style="margin:0;padding:20px;font-family:Arial,sans-serif;background:#f8fafc;">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 6px rgba(0,0,0,0.1);">
  <div style="background:{header_color};color:white;padding:32px;text-align:center;">
    <div style="font-size:48px;margin-bottom:16px;">{icon}</div>
    <h1 style="margin:0;font-size:24px;font-weight:700;">{title}</h1>
    <p style="margin:8px 0 0;font-size:14px;opacity:0.9;">Slot {slot}</p>
  </div>
  
  <div style="padding:32px;text-align:center;">
    <p style="font-size:16px;color:#374151;line-height:1.6;margin-bottom:24px;">{message}</p>
    
    <a href="{cta_url}" 
       style="display:inline-block;background:{header_color};color:white;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:600;">{cta_text}</a>
  </div>
  
  <div style="background:#f9fafb;padding:16px;text-align:center;color:#6b7280;font-size:12px;">
    SmartPark - Intelligent Parking Solutions
  </div>
</div>
</body>
</html>
    '''
    
    return _send_async(to_email, subject, html)


def send_monthly_summary_email(to_email: str, username: str, summary_data: dict):
    """Send monthly parking summary with statistics"""
    base_url = os.environ.get('APP_BASE_URL', 'https://smart-park-z1yb.onrender.com')
    
    total_bookings = summary_data.get('total_bookings', 0)
    total_spent = summary_data.get('total_spent', 0)
    total_hours = summary_data.get('total_hours', 0)
    favorite_slot = summary_data.get('favorite_slot', 'N/A')
    loyalty_points = summary_data.get('loyalty_points', 0)
    month_year = summary_data.get('month_year', datetime.now().strftime('%B %Y'))
    
    html = f'''
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Monthly Parking Summary</title></head>
<body style="margin:0;padding:20px;font-family:Arial,sans-serif;background:#f8fafc;">
<div style="max-width:650px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 6px rgba(0,0,0,0.1);">
  <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;padding:40px;text-align:center;">
    <h1 style="margin:0;font-size:32px;font-weight:700;">Monthly Summary</h1>
    <p style="margin:8px 0 0;font-size:18px;opacity:0.9;">{month_year}</p>
  </div>
  
  <div style="padding:40px;">
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:24px;margin-bottom:32px;">
      <div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:12px;padding:24px;text-align:center;">
        <div style="font-size:36px;font-weight:700;color:#0284c7;margin-bottom:8px;">{total_bookings}</div>
        <div style="color:#0369a1;font-weight:600;">Total Bookings</div>
      </div>
      <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px;padding:24px;text-align:center;">
        <div style="font-size:36px;font-weight:700;color:#059669;margin-bottom:8px;">₹{total_spent}</div>
        <div style="color:#047857;font-weight:600;">Total Spent</div>
      </div>
      <div style="background:#fef3c7;border:1px solid #fbbf24;border-radius:12px;padding:24px;text-align:center;">
        <div style="font-size:36px;font-weight:700;color:#d97706;margin-bottom:8px;">{total_hours}h</div>
        <div style="color:#b45309;font-weight:600;">Parking Hours</div>
      </div>
      <div style="background:#f3e8ff;border:1px solid #c4b5fd;border-radius:12px;padding:24px;text-align:center;">
        <div style="font-size:36px;font-weight:700;color:#7c3aed;margin-bottom:8px;">{loyalty_points}</div>
        <div style="color:#6d28d9;font-weight:600;">Loyalty Points</div>
      </div>
    </div>
    
    <div style="background:#f8fafc;border-radius:12px;padding:24px;margin-bottom:24px;">
      <h3 style="margin:0 0 16px;color:#374151;">Quick Stats</h3>
      <div style="color:#6b7280;line-height:1.8;">
        <div><strong>Favorite Slot:</strong> {favorite_slot}</div>
        <div><strong>Average per Booking:</strong> ₹{round(total_spent/total_bookings) if total_bookings > 0 else 0}</div>
        <div><strong>Average Duration:</strong> {round(total_hours/total_bookings, 1) if total_bookings > 0 else 0} hours</div>
      </div>
    </div>
    
    <div style="text-align:center;">
      <a href="{base_url}/booking/bookings/{username}" 
         style="display:inline-block;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:600;margin-right:12px;">View All Bookings</a>
      <a href="{base_url}/core/dashboard/{username}" 
         style="display:inline-block;background:white;color:#6366f1;border:2px solid #6366f1;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;">Dashboard</a>
    </div>
  </div>
  
  <div style="background:#f9fafb;padding:20px;text-align:center;color:#6b7280;font-size:12px;">
    Thank you for choosing SmartPark! • support@smartpark.com
  </div>
</div>
</body>
</html>
    '''
    
    return _send_async(to_email, f'📊 Your {month_year} Parking Summary', html)


def send_promotional_email(to_email: str, username: str, promo_data: dict):
    """Send promotional emails for offers and updates"""
    base_url = os.environ.get('APP_BASE_URL', 'https://smart-park-z1yb.onrender.com')
    
    title = promo_data.get('title', 'Special Offer')
    description = promo_data.get('description', 'Limited time offer just for you!')
    discount = promo_data.get('discount', 0)
    code = promo_data.get('code', '')
    
    html = f'''
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{title}</title></head>
<body style="margin:0;padding:20px;font-family:Arial,sans-serif;background:#f8fafc;">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 6px rgba(0,0,0,0.1);">
  <div style="background:linear-gradient(135deg,#ec4899,#f97316);color:white;padding:40px;text-align:center;">
    <div style="font-size:48px;margin-bottom:16px;">🎉</div>
    <h1 style="margin:0;font-size:28px;font-weight:700;">{title}</h1>
    <p style="margin:8px 0 0;font-size:16px;opacity:0.9;">Exclusive for {username}</p>
  </div>
  
  <div style="padding:40px;text-align:center;">
    <p style="font-size:18px;color:#374151;line-height:1.6;margin-bottom:24px;">{description}</p>
    
    {f'<div style="background:linear-gradient(135deg,#ec4899,#f97316);color:white;border-radius:12px;padding:24px;margin-bottom:24px;"><div style="font-size:48px;font-weight:700;margin-bottom:8px;">{discount}% OFF</div><div style="font-size:16px;opacity:0.9;">Use code: <strong>{code}</strong></div></div>' if discount > 0 and code else ''}
    
    <a href="{base_url}/booking/book/{username}" 
       style="display:inline-block;background:linear-gradient(135deg,#ec4899,#f97316);color:white;padding:16px 32px;border-radius:8px;text-decoration:none;font-weight:700;font-size:16px;">Book Now</a>
  </div>
  
  <div style="background:#f9fafb;padding:16px;text-align:center;color:#6b7280;font-size:12px;">
    SmartPark - Your Parking Partner
  </div>
</div>
</body>
</html>
    '''
    
    return _send_async(to_email, f'🎉 {title} - SmartPark', html)


def send_test_email(to_email: str, username: str = "Test User"):
    """Send a test email to verify email configuration"""
    html = '''
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Email Test</title></head>
<body style="margin:0;padding:20px;font-family:Arial,sans-serif;background:#f8fafc;">
<div style="max-width:500px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 6px rgba(0,0,0,0.1);">
  <div style="background:#10b981;color:white;padding:32px;text-align:center;">
    <div style="font-size:48px;margin-bottom:16px;">✅</div>
    <h1 style="margin:0;font-size:24px;font-weight:700;">Email Test Successful!</h1>
    <p style="margin:8px 0 0;font-size:14px;opacity:0.9;">SmartPark email system is working</p>
  </div>
  
  <div style="padding:32px;text-align:center;">
    <p style="font-size:16px;color:#374151;line-height:1.6;">
      This is a test email to verify that your SmartPark email configuration is working correctly.
    </p>
    <p style="font-size:14px;color:#6b7280;margin-top:24px;">
      Sent at: ''' + datetime.now().strftime('%d %b %Y, %I:%M %p') + '''
    </p>
  </div>
  
  <div style="background:#f9fafb;padding:16px;text-align:center;color:#6b7280;font-size:12px;">
    SmartPark Email System
  </div>
</div>
</body>
</html>
    '''
    
    return _send_async(to_email, '✅ SmartPark Email Test', html)