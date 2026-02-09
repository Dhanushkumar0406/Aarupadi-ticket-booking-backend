import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas


def generate_ticket_pdf(user, ticket):
    """Generate a PDF ticket and return bytes."""
    buf = io.BytesIO()
    w, h = A4
    c = canvas.Canvas(buf, pagesize=A4)

    # Colours
    primary = HexColor("#8B1A1A")
    dark = HexColor("#333333")
    light_bg = HexColor("#FFF5F0")
    green = HexColor("#2E7D32")

    # Background card
    card_x, card_y, card_w, card_h = 30 * mm, h - 250 * mm, 150 * mm, 230 * mm
    c.setFillColor(light_bg)
    c.roundRect(card_x, card_y, card_w, card_h, 10, fill=1, stroke=0)

    # Header band
    c.setFillColor(primary)
    c.roundRect(card_x, card_y + card_h - 40 * mm, card_w, 40 * mm, 10, fill=1, stroke=0)
    c.rect(card_x, card_y + card_h - 40 * mm, card_w, 20 * mm, fill=1, stroke=0)

    # Title
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(w / 2, card_y + card_h - 22 * mm, "MURUGAN TEMPLE TOUR")
    c.setFont("Helvetica", 11)
    c.drawCentredString(w / 2, card_y + card_h - 32 * mm, "Official Ticket")

    # Divider
    y = card_y + card_h - 50 * mm
    c.setStrokeColor(primary)
    c.setLineWidth(0.5)
    c.line(card_x + 10 * mm, y, card_x + card_w - 10 * mm, y)

    # Details
    left = card_x + 15 * mm
    label_font = ("Helvetica", 9)
    value_font = ("Helvetica-Bold", 12)
    line_gap = 22 * mm

    def draw_field(label, value, ypos):
        c.setFillColor(HexColor("#888888"))
        c.setFont(*label_font)
        c.drawString(left, ypos, label)
        c.setFillColor(dark)
        c.setFont(*value_font)
        c.drawString(left, ypos - 6 * mm, str(value))

    y -= 10 * mm
    draw_field("Ticket No", f"#MT-{ticket.id:05d}", y)
    y -= line_gap
    draw_field("Passenger Name", user.full_name, y)
    y -= line_gap
    draw_field("Citizen ID", user.citizen_id, y)
    y -= line_gap
    draw_field("Package", ticket.temple_name, y)
    y -= line_gap
    draw_field("Boarding Point", ticket.boarding_point, y)
    y -= line_gap
    draw_field("Age", str(ticket.age), y)

    # Cost badge
    y -= line_gap
    c.setFont(*label_font)
    c.setFillColor(HexColor("#888888"))
    c.drawString(left, y, "Amount")
    if ticket.is_free:
        c.setFillColor(green)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(left, y - 7 * mm, "FREE")
    else:
        c.setFillColor(primary)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(left, y - 7 * mm, f"Rs. {ticket.cost}")

    # Date
    y -= line_gap
    draw_field("Booked On", ticket.created_at.strftime("%d-%b-%Y %I:%M %p"), y)

    # Footer
    c.setFillColor(HexColor("#AAAAAA"))
    c.setFont("Helvetica", 8)
    c.drawCentredString(w / 2, card_y + 8 * mm, "This is a computer-generated ticket. No signature required.")

    c.save()
    buf.seek(0)
    return buf.getvalue()
