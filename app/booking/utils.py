import base64
import logging
import traceback
from io import BytesIO
from typing import Optional

logger = logging.getLogger(__name__)


def generate_qr_base64(data: str) -> str:
    """Return a base64-encoded PNG of a QR code, or empty string on failure."""
    try:
        import qrcode
        qr = qrcode.QRCode(version=5, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=6, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except (ImportError, ValueError, OSError) as e:
        logger.warning("QR generation failed: %s", e)
        return ""


def generate_pdf_ticket(booking) -> Optional[bytes]:
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.utils import ImageReader
        from reportlab.lib import colors
        from datetime import datetime, timedelta

        # Convert sqlite3.Row to plain dict safely
        b = dict(zip(booking.keys(), tuple(booking)))

        buf = BytesIO()
        p = canvas.Canvas(buf, pagesize=A4)
        W, H = A4

        # ── Time calculations ──────────────────────────────────────────────
        raw_start = b.get('start_time') or str(b.get('created_at', ''))[:16]
        start_dt = None
        for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M'):
            try:
                start_dt = datetime.strptime(raw_start[:16], fmt)
                break
            except ValueError:
                pass
        if start_dt:
            end_dt = start_dt + timedelta(hours=b.get('duration_hours') or 1)
            start_str = start_dt.strftime('%d %b %Y, %I:%M %p')
            end_str   = end_dt.strftime('%d %b %Y, %I:%M %p')
        else:
            start_str = raw_start
            end_str   = 'N/A'

        # ── Payment breakdown ──────────────────────────────────────────────
        duration      = b.get('duration_hours') or 1
        amount_paid   = int(b.get('amount_paid') or 0)
        loyalty_disc  = int(b.get('loyalty_discount') or 0)
        is_peak       = bool(b.get('peak_booking'))
        # Reverse-calculate base: amount_paid = base * multiplier - loyalty
        # We store peak_booking flag; show multiplier as 1.5x if peak else 1x
        multiplier    = 1.5 if is_peak else 1.0
        base_amount   = round((amount_paid + loyalty_disc) / multiplier)
        peak_surcharge = round(base_amount * multiplier) - base_amount

        # ── QR code ────────────────────────────────────────────────────────
        vehicle_plate = b.get('vehicle_plate') or ''
        qr_data = (
            f"=== SMARTPARK TICKET ===\n"
            f"Ticket ID : #{b['id']}\n"
            f"Customer  : {b['username']}\n"
            f"Slot      : {b['slot']}\n"
            f"Vehicle   : {b['vehicle']}"
            + (f" ({vehicle_plate})" if vehicle_plate else "") + "\n"
            f"Start     : {start_str}\n"
            f"End       : {end_str}\n"
            f"Duration  : {duration}h\n"
            f"Amount    : Rs.{amount_paid}\n"
            f"Status    : {(b.get('status') or 'active').upper()}\n"
            f"======================="
        )
        qr_b64 = generate_qr_base64(qr_data)

        # ══════════════════════════════════════════════════════════════════
        # HEADER
        # ══════════════════════════════════════════════════════════════════
        p.setFillColorRGB(0.09, 0.24, 0.57)
        p.rect(0, H - 90, W, 90, stroke=0, fill=1)

        # Logo area
        p.setFillColorRGB(1, 1, 1)
        p.setFont("Helvetica-Bold", 24)
        p.drawString(45, H - 42, "SmartPark")
        p.setFont("Helvetica", 10)
        p.setFillColorRGB(0.7, 0.85, 1.0)
        p.drawString(45, H - 58, "Professional Parking Invoice")
        p.setFont("Helvetica", 9)
        p.drawString(45, H - 72, "Secure  ·  Convenient  ·  Efficient")

        # Invoice meta (top-right)
        p.setFillColorRGB(1, 1, 1)
        p.setFont("Helvetica-Bold", 11)
        p.drawRightString(W - 45, H - 38, f"INVOICE #{b['id']:05d}")
        p.setFont("Helvetica", 9)
        p.setFillColorRGB(0.7, 0.85, 1.0)
        status_label = (b.get('status') or 'active').upper()
        p.drawRightString(W - 45, H - 54, f"Status: {status_label}")
        p.drawRightString(W - 45, H - 68, f"Date: {str(b.get('created_at', ''))[:10]}")

        # ══════════════════════════════════════════════════════════════════
        # BILL TO / BOOKING INFO  (two-column)
        # ══════════════════════════════════════════════════════════════════
        y_section = H - 115
        # Left: Bill To
        p.setFillColorRGB(0.09, 0.24, 0.57)
        p.setFont("Helvetica-Bold", 9)
        p.drawString(45, y_section, "BILL TO")
        p.setFillColorRGB(0.1, 0.1, 0.1)
        p.setFont("Helvetica-Bold", 12)
        p.drawString(45, y_section - 16, b['username'])
        p.setFont("Helvetica", 9)
        p.setFillColorRGB(0.4, 0.4, 0.4)
        p.drawString(45, y_section - 30, f"Vehicle: {b['vehicle']}"
                     + (f"  ·  Plate: {vehicle_plate}" if vehicle_plate else ""))

        # Right: Booking details
        p.setFillColorRGB(0.09, 0.24, 0.57)
        p.setFont("Helvetica-Bold", 9)
        p.drawString(W // 2 + 20, y_section, "BOOKING DETAILS")
        details_right = [
            ("Parking Slot", b['slot']),
            ("Start Time",   start_str),
            ("End Time",     end_str),
            ("Duration",     f"{duration} hour(s)"),
        ]
        dy = y_section - 16
        for lbl, val in details_right:
            p.setFont("Helvetica", 8)
            p.setFillColorRGB(0.5, 0.5, 0.5)
            p.drawString(W // 2 + 20, dy, lbl)
            p.setFont("Helvetica-Bold", 9)
            p.setFillColorRGB(0.1, 0.1, 0.1)
            p.drawString(W // 2 + 110, dy, val)
            dy -= 14

        # Divider
        div_y = y_section - 58
        p.setStrokeColorRGB(0.85, 0.88, 0.95)
        p.setLineWidth(0.8)
        p.line(45, div_y, W - 45, div_y)

        # ══════════════════════════════════════════════════════════════════
        # PAYMENT BREAKDOWN TABLE
        # ══════════════════════════════════════════════════════════════════
        tbl_y = div_y - 18
        col_desc  = 45
        col_qty   = 280
        col_rate  = 360
        col_amt   = W - 45
        row_h     = 22

        # Table header
        p.setFillColorRGB(0.09, 0.24, 0.57)
        p.rect(45, tbl_y - 4, W - 90, row_h, stroke=0, fill=1)
        p.setFillColorRGB(1, 1, 1)
        p.setFont("Helvetica-Bold", 9)
        p.drawString(col_desc + 6, tbl_y + 5, "DESCRIPTION")
        p.drawString(col_qty,      tbl_y + 5, "QTY")
        p.drawString(col_rate,     tbl_y + 5, "RATE")
        p.drawRightString(col_amt, tbl_y + 5, "AMOUNT")

        # Table rows
        vehicle_rate = base_amount // duration if duration else base_amount
        rows = [
            (f"Parking – {b['vehicle']} ({b['slot']})", f"{duration} hr", f"Rs.{vehicle_rate}/hr", f"Rs.{base_amount}"),
        ]
        if is_peak:
            rows.append(("Peak Hour Surcharge (1.5×)", "—", "—", f"Rs.{peak_surcharge}"))
        if loyalty_disc > 0:
            rows.append(("Loyalty Discount", "—", "—", f"-Rs.{loyalty_disc}"))

        row_y = tbl_y - row_h
        for i, (desc, qty, rate, amt) in enumerate(rows):
            if i % 2 == 0:
                p.setFillColorRGB(0.96, 0.97, 1.0)
                p.rect(45, row_y - 4, W - 90, row_h, stroke=0, fill=1)
            p.setFillColorRGB(0.15, 0.15, 0.15)
            p.setFont("Helvetica", 9)
            p.drawString(col_desc + 6, row_y + 5, desc)
            p.drawString(col_qty,      row_y + 5, qty)
            p.drawString(col_rate,     row_y + 5, rate)
            p.setFont("Helvetica-Bold", 9)
            p.drawRightString(col_amt, row_y + 5, amt)
            row_y -= row_h

        # Total row
        p.setFillColorRGB(0.09, 0.24, 0.57)
        p.rect(45, row_y - 6, W - 90, 28, stroke=0, fill=1)
        p.setFillColorRGB(1, 1, 1)
        p.setFont("Helvetica-Bold", 11)
        p.drawString(col_desc + 6, row_y + 8, "TOTAL AMOUNT PAID")
        p.drawRightString(col_amt, row_y + 8, f"Rs.{amount_paid}")
        row_y -= 28

        # Payment method note
        p.setFillColorRGB(0.93, 0.97, 0.93)
        p.roundRect(45, row_y - 22, W - 90, 18, 4, stroke=0, fill=1)
        p.setFillColorRGB(0.06, 0.5, 0.2)
        p.setFont("Helvetica-Bold", 8)
        p.drawString(55, row_y - 13, "✓  Payment Received  ·  Online / UPI / Cash at Counter")
        row_y -= 30

        # ══════════════════════════════════════════════════════════════════
        # QR CODE + TERMS  (side by side)
        # ══════════════════════════════════════════════════════════════════
        qr_section_y = row_y - 10
        qr_size = 150
        if qr_b64:
            qr_img = ImageReader(BytesIO(base64.b64decode(qr_b64)))
            p.drawImage(qr_img, 45, qr_section_y - qr_size, width=qr_size, height=qr_size,
                        preserveAspectRatio=True)
        p.setFont("Helvetica", 7)
        p.setFillColorRGB(0.5, 0.5, 0.5)
        p.drawCentredString(45 + qr_size / 2, qr_section_y - qr_size - 10, "Scan at entrance")

        # Terms
        terms = [
            "Terms & Conditions",
            "1. This invoice is auto-generated and valid without signature.",
            "2. Booking is non-transferable.",
            "3. Overstay beyond booked duration will incur extra charges.",
            "4. SmartPark is not liable for vehicle damage or theft.",
            "5. For support: support@smartpark.in",
        ]
        tx = 45 + qr_size + 20
        ty = qr_section_y - 4
        for i, line in enumerate(terms):
            p.setFont("Helvetica-Bold" if i == 0 else "Helvetica", 8 if i == 0 else 7.5)
            p.setFillColorRGB(0.09, 0.24, 0.57 if i == 0 else 0.4)
            p.drawString(tx, ty, line)
            ty -= 13

        # ══════════════════════════════════════════════════════════════════
        # FOOTER
        # ══════════════════════════════════════════════════════════════════
        p.setFillColorRGB(0.09, 0.24, 0.57)
        p.rect(0, 0, W, 30, stroke=0, fill=1)
        p.setFillColorRGB(1, 1, 1)
        p.setFont("Helvetica", 8)
        p.drawCentredString(W / 2, 11, "Present this invoice at the parking entrance  |  SmartPark  |  www.smartpark.in")

        p.save()
        buf.seek(0)
        pdf_bytes = buf.getvalue()
        buf.close()
        return pdf_bytes

    except Exception as e:
        logger.error("PDF generation error: %s\n%s", e, traceback.format_exc())
        return None
