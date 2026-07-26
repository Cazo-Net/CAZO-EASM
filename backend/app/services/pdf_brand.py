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

def draw_logo(size: float = 36) -> Group:
    """Return a Group containing the CAZO shield logo scaled to *size* pt."""
    s = size / 200  # SVG viewBox is 200x200
    g = Group()

    # Shield body
    g.add(_path("M100,38 140,58 140,108 Q140,138 100,160 60,138 60,108 60,58 Z",
               fill=DARK, stroke=BLUE, stroke_w=2.5 * s))
    # Inner accent
    g.add(_path("M100,48 132,64 132,104 Q132,130 100,148 68,130 68,104 68,64 Z",
               fill=None, stroke=BLUE, stroke_w=0.8 * s, opacity=0.3))
    # Crosshair lines
    for x1, y1, x2, y2 in [(100,70,100,85),(100,115,100,130),(80,100,95,100),(105,100,120,100)]:
        g.add(Line(x1*s, y1*s, x2*s, y2*s, strokeColor=RED, strokeWidth=1.5*s, strokeOpacity=0.85))
    # Target circles
    g.add(Circle(100*s, 100*s, 12*s, fillColor=None, strokeColor=RED, strokeWidth=1.5*s, strokeOpacity=0.7))
    g.add(Circle(100*s, 100*s, 6*s, fillColor=None, strokeColor=RED, strokeWidth=1*s, strokeOpacity=0.5))
    g.add(Circle(100*s, 100*s, 2*s, fillColor=RED, strokeColor=None, fillOpacity=0.9))

    g.transform = (s, 0, 0, s, 0, 0)
    return g


def _path(d: str, fill=None, stroke=None, stroke_w=1, opacity=1):
    """Minimal SVG-path-to-ReportLab shim for the shield shapes."""
    from reportlab.graphics.shapes import Path
    p = Path(d, fillColor=fill, strokeColor=stroke or fill, strokeWidth=stroke_w)
    if opacity != 1:
        p.fillOpacity = opacity
        p.strokeOpacity = opacity
    return p


# ══════════════════════════════════════════════════════════════════════
# COMPANY SEAL  —  circular, drawn entirely in ReportLab
# ══════════════════════════════════════════════════════════════════════

def draw_seal(size: float = 120) -> Drawing:
    """Return a Drawing of the CAZO circular seal."""
    d = Drawing(size, size)
    cx, cy = size / 2, size / 2
    r_outer = size / 2 - 2
    r_inner = r_outer - 8

    # Outer ring
    d.add(Circle(cx, cy, r_outer, fillColor=None, strokeColor=BLUE, strokeWidth=2))
    d.add(Circle(cx, cy, r_inner, fillColor=None, strokeColor=BLUE, strokeWidth=0.5, strokeOpacity=0.4))

    # Shield mini in center
    sc = size / 200
    shield_g = Group()
    shield_g.add(_path("M100,55 128,68 128,100 Q128,120 100,132 72,120 72,100 72,68 Z",
                       fill=DARK, stroke=BLUE, stroke_w=1.5))
    # Mini crosshair
    shield_g.add(Line(100, 78, 100, 88, strokeColor=RED, strokeWidth=1))
    shield_g.add(Line(100, 112, 100, 122, strokeColor=RED, strokeWidth=1))
    shield_g.add(Line(88, 100, 98, 100, strokeColor=RED, strokeWidth=1))
    shield_g.add(Line(102, 100, 112, 100, strokeColor=RED, strokeWidth=1))
    shield_g.add(Circle(100, 100, 8, fillColor=None, strokeColor=RED, strokeWidth=1, strokeOpacity=0.7))
    shield_g.add(Circle(100, 100, 3, fillColor=RED, strokeColor=None))
    shield_g.transform = (sc * 0.55, 0, 0, sc * 0.55,
                           cx - 100 * sc * 0.55, cy - 100 * sc * 0.55)
    d.add(shield_g)

    # Curved text — outer ring top: "CAZO SECURITY"
    _add_arc_text(d, "CAZO SECURITY", cx, cy, r_outer - 14, start_deg=150, font_size=max(7, size / 18))
    # Curved text — outer ring bottom: "ATTACK SURFACE REPORT"
    _add_arc_text(d, "ATTACK SURFACE REPORT", cx, cy, r_outer - 14, start_deg=330, font_size=max(5.5, size / 24), reverse=True)

    return d


def _add_arc_text(drawing, text, cx, cy, radius, start_deg=90, font_size=8, reverse=False):
    """Place characters along a circular arc."""
    from reportlab.graphics.shapes import String
    n = len(text)
    if n == 0:
        return
    span = min(140, n * (font_size * 0.7))  # total angular span in degrees
    for i, ch in enumerate(text):
        if reverse:
            angle = math.radians(start_deg - (i / max(n - 1, 1)) * span)
        else:
            angle = math.radians(start_deg - (i / max(n - 1, 1)) * span)
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        s = String(x, y, ch, fontSize=font_size, fillColor=BLUE,
                   textAnchor="middle", fontName="Helvetica-Bold")
        # Rotate character to follow the arc
        deg = math.degrees(angle) - 90
        s.angle = deg
        drawing.add(s)


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
    seal = draw_seal(110)
    renderPDF.draw(seal, canvas, PAGE_W - 170, 60)

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
