"""ReportLab drawing helpers for branded CAZO EASM PDF reports.

All visuals (logo, seal, headers, footers) are drawn purely via ReportLab
graphics primitives — no external image files required.  The color palette
matches the platform's design system:
    Blue   #3B82F6   (primary)
    Cyan   #06B6D4   (accent)
    Red    #EF4444   (crosshair / severity-critical)
    Dark   #09090B   (backgrounds)
"""
import math
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Flowable
from reportlab.graphics.shapes import Drawing, Circle, Line, String, Rect, Wedge, Group
from reportlab.graphics import renderPDF

# ── Brand palette ──────────────────────────────────────────────────────
BLUE = colors.HexColor("#3B82F6")
CYAN = colors.HexColor("#06B6D4")
RED = colors.HexColor("#EF4444")
DARK = colors.HexColor("#09090B")
DARK_CARD = colors.HexColor("#111827")
MUTED = colors.HexColor("#6B7280")
LIGHT_BG = colors.HexColor("#F9FAFB")
WHITE = colors.white
PAGE_W, PAGE_H = A4  # 595.27 x 841.89 pt


# ══════════════════════════════════════════════════════════════════════
# LOGO  —  vector shield + crosshair drawn in ReportLab
# ══════════════════════════════════════════════════════════════════════

def draw_logo(size: float = 36) -> Drawing:
    """Return a Drawing containing the CAZO shield logo scaled to *size* pt."""
    s = size / 200  # viewBox is 200x200
    d = Drawing(size, size)
    g = Group()

    # Shield body polygon
    shield_pts = [
        100,38, 140,58, 140,108, 136,127, 122,145,
        100,160, 78,145, 64,127, 60,108, 60,58,
    ]
    g.add(_polygon(shield_pts, fill=DARK, stroke=BLUE, stroke_w=2.5))
    # Inner accent
    accent_pts = [
        100,48, 132,64, 132,104, 129,120, 118,135,
        100,148, 82,135, 71,120, 68,104, 68,64,
    ]
    g.add(_polygon(accent_pts, fill=None, stroke=BLUE, stroke_w=0.8, opacity=0.3))
    # Crosshair lines
    for x1, y1, x2, y2 in [(100,70,100,85),(100,115,100,130),(80,100,95,100),(105,100,120,100)]:
        g.add(Line(x1, y1, x2, y2, strokeColor=RED, strokeWidth=1.5, strokeOpacity=0.85))
    # Target circles
    g.add(Circle(100, 100, 12, fillColor=None, strokeColor=RED, strokeWidth=1.5, strokeOpacity=0.7))
    g.add(Circle(100, 100, 6, fillColor=None, strokeColor=RED, strokeWidth=1, strokeOpacity=0.5))
    g.add(Circle(100, 100, 2, fillColor=RED, strokeColor=None, fillOpacity=0.9))

    g.transform = (s, 0, 0, s, 0, 0)
    d.add(g)
    return d


def _polygon(points, fill=None, stroke=None, stroke_w=1, opacity=1):
    """Draw a closed polygon from a flat list of [x1,y1,x2,y2,...] coordinates."""
    from reportlab.graphics.shapes import Polygon
    p = Polygon(points=points,
                fillColor=fill, strokeColor=stroke or fill, strokeWidth=stroke_w)
    if opacity != 1:
        p.fillOpacity = opacity
        p.strokeOpacity = opacity
    return p


def _path(d: str, fill=None, stroke=None, stroke_w=1, opacity=1):
    """Minimal SVG-path-to-ReportLab shim — only supports M/L/Z (no curves)."""
    from reportlab.graphics.shapes import Path
    p = Path(d, fillColor=fill, strokeColor=stroke or fill, strokeWidth=stroke_w)
    if opacity != 1:
        p.fillOpacity = opacity
        p.strokeOpacity = opacity
    return p


# ══════════════════════════════════════════════════════════════════════
# COMPANY SEAL  —  circular, drawn entirely in ReportLab
# ══════════════════════════════════════════════════════════════════════

def draw_seal(canvas, cx: float, cy: float, size: float = 110):
    """Draw the CAZO circular seal directly onto *canvas* centered at (cx, cy)."""
    r_outer = size / 2 - 2
    r_inner = r_outer - 8

    # Outer ring
    canvas.saveState()
    canvas.setStrokeColor(BLUE)
    canvas.setLineWidth(2)
    canvas.circle(cx, cy, r_outer, fill=0, stroke=1)
    canvas.setLineWidth(0.5)
    canvas.setStrokeAlpha(0.4)
    canvas.circle(cx, cy, r_inner, fill=0, stroke=1)
    canvas.restoreState()

    # Shield mini in center (drawn with canvas primitives)
    sc = (size / 200) * 0.55
    sx = cx - 100 * sc
    sy = cy - 100 * sc

    shield_pts = [
        (100,55), (128,68), (128,100), (125,112), (115,123),
        (100,132), (85,123), (75,112), (72,100), (72,68),
    ]
    canvas.saveState()
    canvas.setFillColor(DARK)
    canvas.setStrokeColor(BLUE)
    canvas.setLineWidth(1.5)
    path = canvas.beginPath()
    path.moveTo(sx + shield_pts[0][0] * sc, sy + shield_pts[0][1] * sc)
    for px, py in shield_pts[1:]:
        path.lineTo(sx + px * sc, sy + py * sc)
    path.close()
    canvas.drawPath(path, fill=1, stroke=1)
    canvas.restoreState()

    # Mini crosshair
    canvas.saveState()
    canvas.setStrokeColor(RED)
    canvas.setLineWidth(1)
    canvas.line(cx, cy - 22 * sc, cx, cy - 12 * sc)
    canvas.line(cx, cy + 12 * sc, cx, cy + 22 * sc)
    canvas.line(cx - 12 * sc, cy, cx - 2 * sc, cy)
    canvas.line(cx + 2 * sc, cy, cx + 12 * sc, cy)
    canvas.setStrokeAlpha(0.7)
    canvas.circle(cx, cy, 8 * sc, fill=0, stroke=1)
    canvas.setFillColor(RED)
    canvas.circle(cx, cy, 3 * sc, fill=1, stroke=0)
    canvas.restoreState()

    # Curved text — outer ring top: "CAZO SECURITY"
    _draw_arc_text_on_canvas(canvas, "CAZO SECURITY", cx, cy, r_outer - 14,
                             start_deg=150, font_size=max(7, size / 18))
    # Curved text — outer ring bottom: "ATTACK SURFACE REPORT"
    _draw_arc_text_on_canvas(canvas, "ATTACK SURFACE REPORT", cx, cy, r_outer - 14,
                             start_deg=330, font_size=max(5.5, size / 24), bottom=True)


def _draw_arc_text_on_canvas(canvas, text, cx, cy, radius, start_deg=90, font_size=8, bottom=False):
    """Draw rotated text along a circular arc directly on canvas."""
    n = len(text)
    if n == 0:
        return
    span = min(140, n * (font_size * 0.7))
    canvas.saveState()
    canvas.setFillColor(BLUE)
    canvas.setFont("Helvetica-Bold", font_size)
    for i, ch in enumerate(text):
        if bottom:
            # Bottom arc: text reads left-to-right, characters face inward
            angle = start_deg + (i / max(n - 1, 1)) * span
            rad = math.radians(angle)
            x = cx + radius * math.cos(rad)
            y = cy + radius * math.sin(rad)
            canvas.saveState()
            canvas.translate(x, y)
            canvas.rotate(angle + 90)
            canvas.drawCentredString(0, -font_size * 0.3, ch)
            canvas.restoreState()
        else:
            # Top arc: text reads left-to-right, characters face outward
            angle = start_deg - (i / max(n - 1, 1)) * span
            rad = math.radians(angle)
            x = cx + radius * math.cos(rad)
            y = cy + radius * math.sin(rad)
            canvas.saveState()
            canvas.translate(x, y)
            canvas.rotate(angle - 90)
            canvas.drawCentredString(0, -font_size * 0.3, ch)
            canvas.restoreState()
    canvas.restoreState()


# ══════════════════════════════════════════════════════════════════════
# PAGE HEADER  —  drawn on every page via onPage callback
# ══════════════════════════════════════════════════════════════════════

def draw_page_header(canvas, doc, report_id: str = ""):
    """Branded header drawn at the top of every content page."""
    canvas.saveState()
    # Blue accent line
    canvas.setStrokeColor(BLUE)
    canvas.setLineWidth(1.5)
    canvas.line(50, PAGE_H - 35, PAGE_W - 50, PAGE_H - 35)
    # Logo (small)
    logo = draw_logo(22)
    renderPDF.draw(logo, canvas, 50, PAGE_H - 32)
    # "CAZO EASM" text
    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(DARK)
    canvas.drawString(78, PAGE_H - 28, "CAZO EASM")
    # Report ID right-aligned
    if report_id:
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(PAGE_W - 50, PAGE_H - 28, f"Report {report_id}")
    canvas.restoreState()


# ══════════════════════════════════════════════════════════════════════
# PAGE FOOTER  —  drawn on every page via onPage callback
# ══════════════════════════════════════════════════════════════════════

def draw_page_footer(canvas, doc):
    """Footer with page number, confidentiality notice, and blue accent line."""
    canvas.saveState()
    # Blue accent line
    canvas.setStrokeColor(BLUE)
    canvas.setLineWidth(0.75)
    canvas.line(50, 42, PAGE_W - 50, 42)
    # Page number
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    page_num = canvas.getPageNumber()
    canvas.drawString(50, 30, f"Page {page_num}")
    # Confidentiality notice
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(RED)
    canvas.drawCentredString(PAGE_W / 2, 30, "CONFIDENTIAL")
    # Timestamp
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    from datetime import datetime, timezone
    canvas.drawRightString(PAGE_W - 50, 30, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    canvas.restoreState()


# ══════════════════════════════════════════════════════════════════════
# COVER PAGE  —  first page only
# ══════════════════════════════════════════════════════════════════════

def draw_cover_page(canvas, doc, domain: str, scan_type: str, status: str,
                    completed_at: str, report_id: str):
    """Full-bleed cover page drawn via canvas (called before content)."""
    canvas.saveState()

    # ── Top dark bar ──────────────────────────────────────────────────
    bar_h = 220
    canvas.setFillColor(DARK)
    canvas.rect(0, PAGE_H - bar_h, PAGE_W, bar_h, fill=1, stroke=0)

    # Logo in dark bar
    logo = draw_logo(70)
    renderPDF.draw(logo, canvas, 60, PAGE_H - 180)

    # "CAZO" large text
    canvas.setFont("Helvetica-Bold", 38)
    canvas.setFillColor(WHITE)
    canvas.drawString(140, PAGE_H - 110, "CAZO")

    # Subtitle
    canvas.setFont("Helvetica", 13)
    canvas.setFillColor(CYAN)
    canvas.drawString(140, PAGE_H - 132, "External Attack Surface Management")

    # Red accent line under subtitle
    canvas.setStrokeColor(RED)
    canvas.setLineWidth(2)
    canvas.line(140, PAGE_H - 142, 340, PAGE_H - 142)

    # Report title
    canvas.setFont("Helvetica-Bold", 11)
    canvas.setFillColor(WHITE)
    canvas.drawString(140, PAGE_H - 168, "Scan Report")

    # ── Report ID badge ───────────────────────────────────────────────
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(140, PAGE_H - 195, f"Report Ref: {report_id}")

    # ── Domain card ───────────────────────────────────────────────────
    card_y = PAGE_H - bar_h - 100
    card_h = 80
    # Card background
    canvas.setFillColor(LIGHT_BG)
    canvas.roundRect(50, card_y, PAGE_W - 100, card_h, 6, fill=1, stroke=0)
    # Card border
    canvas.setStrokeColor(colors.HexColor("#E5E7EB"))
    canvas.setLineWidth(0.75)
    canvas.roundRect(50, card_y, PAGE_W - 100, card_h, 6, fill=0, stroke=1)
    # Domain label
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(MUTED)
    canvas.drawString(70, card_y + card_h - 22, "TARGET DOMAIN")
    # Domain value
    canvas.setFont("Helvetica-Bold", 20)
    canvas.setFillColor(DARK)
    canvas.drawString(70, card_y + card_h - 50, domain)

    # ── Scan metadata ─────────────────────────────────────────────────
    meta_y = card_y - 60
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(MUTED)
    labels = ["Scan Type", "Status", "Completed"]
    values = [scan_type.upper(), status.upper(), completed_at or "In Progress"]
    for i, (label, value) in enumerate(zip(labels, values)):
        x = 70 + i * 170
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(x, meta_y + 20, label)
        canvas.setFont("Helvetica-Bold", 10)
        canvas.setFillColor(DARK)
        canvas.drawString(x, meta_y, value)

    # ── Company seal (bottom-right) ───────────────────────────────────
    draw_seal(canvas, PAGE_W - 115, 115, size=110)

    # ── Confidentiality notice (bottom-left) ──────────────────────────
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(RED)
    canvas.drawString(60, 90, "CONFIDENTIAL")
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(60, 78, "This report contains security-sensitive information.")
    canvas.drawString(60, 68, "Distribution restricted to authorized personnel only.")
    canvas.drawString(60, 58, f"Generated by CAZO EASM  |  Report {report_id}")

    # ── Bottom accent line ────────────────────────────────────────────
    canvas.setStrokeColor(BLUE)
    canvas.setLineWidth(2)
    canvas.line(50, 45, PAGE_W - 50, 45)

    canvas.restoreState()


# ══════════════════════════════════════════════════════════════════════
# SECTION HEADING  —  reusable styled heading for content pages
# ══════════════════════════════════════════════════════════════════════

class SectionHeading(Flowable):
    """A blue left-accented section heading."""

    def __init__(self, text: str, width: float = None):
        super().__init__()
        self.text = text
        self._width = width or (PAGE_W - 100)
        self.height = 24

    def wrap(self, availWidth, availHeight):
        return self._width, self.height

    def draw(self):
        c = self.canv
        # Blue left accent bar
        c.setFillColor(BLUE)
        c.rect(0, 2, 3, self.height - 4, fill=1, stroke=0)
        # Text
        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(DARK)
        c.drawString(10, 6, self.text)


# ══════════════════════════════════════════════════════════════════════
# STYLED TABLE HELPERS
# ══════════════════════════════════════════════════════════════════════

def branded_table_style(header_color=BLUE, alt_row=LIGHT_BG):
    """Return a base TableStyle for branded data tables."""
    from reportlab.lib.styles import getSampleStyleSheet
    return [
        ('BACKGROUND', (0, 0), (-1, 0), header_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, alt_row]),
    ]


def severity_color(severity: str) -> colors.Color:
    """Map severity string to a color."""
    return {
        "critical": RED,
        "high": colors.HexColor("#F97316"),
        "medium": colors.HexColor("#EAB308"),
        "low": CYAN,
    }.get(severity.lower() if severity else "", MUTED)
