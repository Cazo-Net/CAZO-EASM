"""Scheduled email reports: a recurring security summary for an organization.

A schedule says when (weekly or monthly, at a local hour in a time zone) and
to whom. When it is due, ``run_due_reports`` builds the organization's summary
for the period just ended, renders an email (and optionally a PDF) and sends
it to each recipient.

Everything in a report is read with the organization's id as a filter; a
report never contains another organization's data.
"""
from __future__ import annotations

import html
import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import frontend_url
from app.models.report_schedule import ReportSchedule

logger = logging.getLogger(__name__)

MAX_SCHEDULES_PER_ORG = 10
MAX_RECIPIENTS = 20
SEVERITIES = ["critical", "high", "medium", "low", "info"]
_SEV_COLOR = {"critical": "#B91C1C", "high": "#C2410C", "medium": "#A16207", "low": "#15803D", "info": "#4B5563"}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ── Schedule arithmetic ──────────────────────────────────────────────────


def get_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return ZoneInfo("UTC")


def is_valid_zone(name: str) -> bool:
    try:
        ZoneInfo(name)
        return True
    except (ZoneInfoNotFoundError, ValueError, OSError, TypeError):
        return False


def compute_next_run(
    frequency: str, weekday: int, day_of_month: int, hour: int, tz_name: str,
    after: Optional[datetime] = None,
) -> datetime:
    """The first scheduled moment strictly after ``after`` (default: now), in UTC."""
    after = after or datetime.now(timezone.utc)
    zone = get_zone(tz_name)
    local = after.astimezone(zone)
    if frequency == "monthly":
        year, month = local.year, local.month
        for _ in range(3):
            candidate = datetime(year, month, day_of_month, hour, tzinfo=zone)
            if candidate.astimezone(timezone.utc) > after:
                return candidate.astimezone(timezone.utc)
            month += 1
            if month > 12:
                year, month = year + 1, 1
        raise RuntimeError("could not compute next monthly run")
    start = datetime(local.year, local.month, local.day, hour, tzinfo=zone)
    for offset in range(0, 9):
        day = start + timedelta(days=offset)
        # Rebuild from the calendar date so the local hour survives DST changes.
        candidate = datetime(day.year, day.month, day.day, hour, tzinfo=zone)
        if candidate.weekday() == weekday and candidate.astimezone(timezone.utc) > after:
            return candidate.astimezone(timezone.utc)
    raise RuntimeError("could not compute next weekly run")


def period_for(frequency: str, end: datetime) -> Tuple[datetime, datetime]:
    return end - timedelta(days=30 if frequency == "monthly" else 7), end


def describe(schedule: ReportSchedule) -> str:
    when = (
        f"day {schedule.day_of_month} of each month" if schedule.frequency == "monthly"
        else f"every {WEEKDAYS[schedule.weekday % 7]}"
    )
    return f"{when} at {schedule.hour:02d}:00 ({schedule.timezone})"


# ── Data ─────────────────────────────────────────────────────────────────


def _sev_counts(rows) -> Dict[str, int]:
    out = {s: 0 for s in SEVERITIES}
    for sev, count in rows:
        key = (sev or "info").lower()
        out[key if key in out else "info"] += int(count)
    return out


def build_summary(db: Session, organization_id: str, start: datetime, end: datetime) -> Dict[str, Any]:
    """The numbers and lists a report shows, for one organization and period."""
    from app.models.asset_change import AssetChange
    from app.models.asset_inventory import Asset
    from app.models.asset_score import AssetScore
    from app.models.audit import AuditEvent
    from app.models.organization import Organization
    from app.models.scan import Scan
    from app.models.vulnerability import Vulnerability

    org = db.query(Organization).filter(Organization.id == organization_id).first()

    # Findings belong to scans; the scan carries the organization.
    def findings():
        return (
            db.query(Vulnerability)
            .join(Scan, Vulnerability.scan_id == Scan.id)
            .filter(Scan.organization_id == organization_id)
        )

    open_filter = Vulnerability.status.notin_(("resolved", "fixed", "closed", "false_positive", "accepted", "accepted_risk"))
    open_by_sev = _sev_counts(
        findings().filter(open_filter).with_entities(Vulnerability.severity, func.count(Vulnerability.id))
        .group_by(Vulnerability.severity).all()
    )
    new_q = findings().filter(Vulnerability.first_seen >= start, Vulnerability.first_seen < end)
    new_by_sev = _sev_counts(
        new_q.with_entities(Vulnerability.severity, func.count(Vulnerability.id))
        .group_by(Vulnerability.severity).all()
    )
    rank = {s: i for i, s in enumerate(SEVERITIES)}
    new_rows = (
        new_q.filter(Vulnerability.severity.in_(("critical", "high", "medium")))
        .with_entities(Vulnerability.name, Vulnerability.host, Vulnerability.severity, Vulnerability.first_seen)
        .order_by(Vulnerability.first_seen.desc()).limit(200).all()
    )
    new_rows = sorted(new_rows, key=lambda r: rank.get((r.severity or "info").lower(), 9))[:10]

    assets = db.query(Asset).filter(Asset.organization_id == organization_id, Asset.asset_type == "host")
    total_assets = assets.filter(Asset.state == "active").count()
    new_assets = assets.filter(Asset.first_seen >= start, Asset.first_seen < end).count()
    new_asset_rows = (
        assets.filter(Asset.first_seen >= start, Asset.first_seen < end)
        .with_entities(Asset.value).order_by(Asset.first_seen.desc()).limit(8).all()
    )

    change_rows = (
        db.query(AssetChange.event, func.count(AssetChange.id))
        .filter(AssetChange.organization_id == organization_id,
                AssetChange.detected_at >= start, AssetChange.detected_at < end)
        .group_by(AssetChange.event).all()
    )
    changes = {(event or "other"): int(count) for event, count in change_rows}

    scans = db.query(Scan).filter(
        Scan.organization_id == organization_id, Scan.created_at >= start, Scan.created_at < end,
    )
    scans_total = scans.count()
    scans_failed = scans.filter(Scan.status == "failed").count()
    domains = [d for (d,) in scans.with_entities(Scan.domain).distinct().limit(50).all()]

    top = (
        db.query(Asset.value, AssetScore.exposure_score)
        .join(AssetScore, AssetScore.asset_id == Asset.id)
        .filter(AssetScore.organization_id == organization_id, Asset.organization_id == organization_id,
                AssetScore.exposure_score > 0)
        .order_by(AssetScore.exposure_score.desc()).limit(5).all()
    )

    last_audit = (
        db.query(AuditEvent.seq, AuditEvent.hash)
        .filter(AuditEvent.organization_id == organization_id, AuditEvent.seq.isnot(None))
        .order_by(AuditEvent.seq.desc()).first()
    )

    return {
        "organization": org.name if org else "Your organization",
        "period_start": start,
        "period_end": end,
        "open_findings": open_by_sev,
        "open_total": sum(open_by_sev.values()),
        "new_findings": new_by_sev,
        "new_total": sum(new_by_sev.values()),
        "top_new_findings": [
            {"name": r.name, "host": r.host, "severity": (r.severity or "info").lower()} for r in new_rows
        ],
        "total_assets": total_assets,
        "new_assets": new_assets,
        "new_asset_names": [v for (v,) in new_asset_rows],
        "changes": changes,
        "scans_total": scans_total,
        "scans_failed": scans_failed,
        "domains": domains,
        "top_exposed": [{"asset": v, "score": round(float(s or 0), 1)} for v, s in top],
        "audit_seq": last_audit.seq if last_audit else None,
        "audit_hash": last_audit.hash if last_audit else None,
    }


# ── Rendering ────────────────────────────────────────────────────────────


def _fmt_date(dt: datetime, tz_name: str) -> str:
    return dt.astimezone(get_zone(tz_name)).strftime("%d %b %Y")


def headline(summary: Dict[str, Any]) -> str:
    n = summary["new_findings"]
    urgent = n["critical"] + n["high"]
    if urgent:
        parts = []
        if n["critical"]:
            parts.append(f"{n['critical']} critical")
        if n["high"]:
            parts.append(f"{n['high']} high")
        return f"{' and '.join(parts)} new finding{'s' if urgent != 1 else ''} need attention"
    if summary["new_total"]:
        return f"{summary['new_total']} new lower-severity finding{'s' if summary['new_total'] != 1 else ''}"
    if summary["scans_total"] == 0:
        return "No scans ran in this period"
    return "No new findings in this period"


def render_email(summary: Dict[str, Any], schedule_name: str, tz_name: str, frequency: str) -> Tuple[str, str, str]:
    """Returns (subject, html, text)."""
    from app.services.email.templates import _base

    e = html.escape
    org = summary["organization"]
    period = f"{_fmt_date(summary['period_start'], tz_name)} to {_fmt_date(summary['period_end'], tz_name)}"
    label = "Monthly" if frequency == "monthly" else "Weekly"
    head = headline(summary)
    subject = f"{label} security report for {org}: {head}"[:200]

    def stat(value, caption):
        return (
            f'<td style="padding:12px 8px;text-align:center;border:1px solid #E5E7EB;">'
            f'<div style="font-size:22px;font-weight:700;color:#111827;">{value}</div>'
            f'<div style="font-size:11px;color:#6B7280;">{e(caption)}</div></td>'
        )

    sev_cells = "".join(
        f'<td style="padding:6px 8px;text-align:center;font-size:12px;color:{_SEV_COLOR[s]};">'
        f'<strong>{summary["open_findings"][s]}</strong> {s}</td>'
        for s in SEVERITIES[:4]
    )
    finding_rows = "".join(
        f'<tr><td style="padding:6px 8px;border-bottom:1px solid #F3F4F6;font-size:12px;color:{_SEV_COLOR[f["severity"]]};'
        f'font-weight:600;white-space:nowrap;">{e(f["severity"].capitalize())}</td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #F3F4F6;font-size:12px;color:#111827;">{e(f["name"] or "")}'
        f'<div style="color:#6B7280;">{e(f["host"] or "")}</div></td></tr>'
        for f in summary["top_new_findings"]
    )
    findings_block = (
        f'<h3 style="font-size:14px;color:#111827;margin:24px 0 8px;">New findings</h3>'
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{finding_rows}</table>'
        if finding_rows else
        '<p style="font-size:13px;color:#374151;margin:24px 0 0;">No new critical, high or medium findings.</p>'
    )
    assets_block = ""
    if summary["new_asset_names"]:
        names = "".join(f'<li style="font-size:12px;color:#111827;">{e(n)}</li>' for n in summary["new_asset_names"])
        more = summary["new_assets"] - len(summary["new_asset_names"])
        assets_block = (
            f'<h3 style="font-size:14px;color:#111827;margin:24px 0 8px;">New assets</h3><ul style="margin:0;padding-left:18px;">'
            f'{names}</ul>' + (f'<p style="font-size:12px;color:#6B7280;margin:6px 0 0;">and {more} more.</p>' if more > 0 else "")
        )
    exposed_block = ""
    if summary["top_exposed"]:
        rows = "".join(
            f'<tr><td style="padding:4px 8px;font-size:12px;color:#111827;">{e(x["asset"] or "")}</td>'
            f'<td style="padding:4px 8px;font-size:12px;color:#6B7280;text-align:right;">{x["score"]}</td></tr>'
            for x in summary["top_exposed"]
        )
        exposed_block = (
            '<h3 style="font-size:14px;color:#111827;margin:24px 0 8px;">Most exposed assets</h3>'
            f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{rows}</table>'
        )
    audit_block = ""
    if summary["audit_hash"]:
        audit_block = (
            f'<p style="font-size:11px;color:#9CA3AF;margin:24px 0 0;word-break:break-all;">Audit log entry '
            f'#{summary["audit_seq"]} fingerprint: {e(summary["audit_hash"])}. Keep this email to prove later that the '
            f'log has not been shortened.</p>'
        )
    link = frontend_url("/dashboard")
    body = f"""
<h2 style="font-size:18px;color:#111827;margin:0 0 4px;">{e(head)}</h2>
<p style="font-size:13px;color:#6B7280;margin:0 0 20px;">{e(org)} &middot; {e(period)}</p>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
<tr>{stat(summary["new_total"], "new findings")}{stat(summary["open_total"], "open findings")}{stat(summary["total_assets"], "assets")}{stat(summary["new_assets"], "new assets")}{stat(summary["scans_total"], "scans")}</tr>
</table>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top:8px;"><tr>
<td style="padding:6px 8px;font-size:12px;color:#6B7280;">Open now:</td>{sev_cells}</tr></table>
{findings_block}{assets_block}{exposed_block}
<p style="margin:28px 0 0;text-align:center;"><a href="{e(link)}" style="display:inline-block;background:#111827;color:#FFFFFF;text-decoration:none;font-size:13px;font-weight:600;padding:10px 20px;border-radius:8px;">Open CAZO EASM</a></p>
{audit_block}
<p style="font-size:11px;color:#9CA3AF;margin:16px 0 0;">You receive this because an administrator of {e(org)} added you to the report "{e(schedule_name)}". Ask them to remove you if you no longer want it.</p>
"""
    text_lines = [
        f"{label} security report for {org}", period, "", head, "",
        f"New findings: {summary['new_total']}   Open findings: {summary['open_total']}",
        f"Assets: {summary['total_assets']} ({summary['new_assets']} new)   Scans: {summary['scans_total']}",
        "Open now: " + ", ".join(f"{summary['open_findings'][s]} {s}" for s in SEVERITIES[:4]),
        "",
    ]
    for f in summary["top_new_findings"]:
        text_lines.append(f"- [{f['severity']}] {f['name']} ({f['host']})")
    text_lines += ["", f"Open CAZO EASM: {link}"]
    if summary["audit_hash"]:
        text_lines += ["", f"Audit log entry #{summary['audit_seq']} fingerprint: {summary['audit_hash']}"]
    return subject, _base(subject, body, head), "\n".join(text_lines)


def render_pdf(summary: Dict[str, Any], tz_name: str, frequency: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    e = html.escape
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], fontSize=20, alignment=0, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=14)
    small = ParagraphStyle("small", parent=body, fontSize=8, textColor=colors.HexColor("#6B7280"))
    grid = colors.HexColor("#E5E7EB")

    label = "Monthly" if frequency == "monthly" else "Weekly"
    period = f"{_fmt_date(summary['period_start'], tz_name)} to {_fmt_date(summary['period_end'], tz_name)}"
    story: List[Any] = [
        Paragraph(f"{label} security report", h1),
        Paragraph(f"{e(summary['organization'])} &middot; {e(period)}", small),
        Spacer(1, 8),
        Paragraph(e(headline(summary)), ParagraphStyle("lead", parent=body, fontSize=12, leading=16)),
        Spacer(1, 8),
    ]
    stats = Table(
        [[str(summary["new_total"]), str(summary["open_total"]), str(summary["total_assets"]),
          str(summary["new_assets"]), str(summary["scans_total"])],
         ["new findings", "open findings", "assets", "new assets", "scans"]],
        colWidths=[34 * mm] * 5,
    )
    stats.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("FONTSIZE", (0, 0), (-1, 0), 18),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 1), (-1, 1), 8),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#6B7280")), ("BOX", (0, 0), (-1, -1), 0.5, grid),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, grid), ("TOPPADDING", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 16),
    ]))
    story.append(stats)

    story.append(Paragraph("Findings by severity", h2))
    sev = Table(
        [["", *[s.capitalize() for s in SEVERITIES]],
         ["Open now", *[str(summary["open_findings"][s]) for s in SEVERITIES]],
         ["New this period", *[str(summary["new_findings"][s]) for s in SEVERITIES]]],
        colWidths=[40 * mm] + [26 * mm] * 5,
    )
    sev.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"), ("LINEBELOW", (0, 0), (-1, -1), 0.5, grid),
        *[("TEXTCOLOR", (i + 1, 0), (i + 1, 0), colors.HexColor(_SEV_COLOR[s])) for i, s in enumerate(SEVERITIES)],
    ]))
    story.append(sev)

    story.append(Paragraph("New findings", h2))
    if summary["top_new_findings"]:
        rows = [["Severity", "Finding", "Host"]] + [
            [f["severity"].capitalize(), Paragraph(e(f["name"] or ""), body), Paragraph(e(f["host"] or ""), body)]
            for f in summary["top_new_findings"]
        ]
        t = Table(rows, colWidths=[24 * mm, 86 * mm, 60 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.5, grid),
            *[("TEXTCOLOR", (0, i + 1), (0, i + 1), colors.HexColor(_SEV_COLOR[f["severity"]]))
              for i, f in enumerate(summary["top_new_findings"])],
        ]))
        story.append(t)
        if summary["new_total"] > len(summary["top_new_findings"]):
            story.append(Paragraph(
                f"Showing the {len(summary['top_new_findings'])} most severe of {summary['new_total']} new findings.", small))
    else:
        story.append(Paragraph("No new critical, high or medium findings in this period.", body))

    if summary["new_asset_names"]:
        story.append(Paragraph("New assets", h2))
        for name in summary["new_asset_names"]:
            story.append(Paragraph("&bull; " + e(name), body))
        more = summary["new_assets"] - len(summary["new_asset_names"])
        if more > 0:
            story.append(Paragraph(f"and {more} more.", small))

    if summary["top_exposed"]:
        story.append(Paragraph("Most exposed assets", h2))
        t = Table([["Asset", "Exposure score"]] + [[Paragraph(e(x["asset"] or ""), body), str(x["score"])]
                                                    for x in summary["top_exposed"]],
                  colWidths=[130 * mm, 40 * mm])
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("LINEBELOW", (0, 0), (-1, -1), 0.5, grid),
        ]))
        story.append(t)

    story.append(Paragraph("Scanning", h2))
    scan_text = f"{summary['scans_total']} scan{'s' if summary['scans_total'] != 1 else ''} ran in this period"
    if summary["scans_failed"]:
        scan_text += f", {summary['scans_failed']} failed"
    if summary["domains"]:
        shown = ", ".join(summary["domains"][:12])
        scan_text += f". Domains covered: {e(shown)}" + (" and others" if len(summary["domains"]) > 12 else "")
    story.append(Paragraph(scan_text + ".", body))

    if summary["audit_hash"]:
        story.append(Spacer(1, 14))
        story.append(Paragraph(
            f"Audit log entry #{summary['audit_seq']} fingerprint: {e(summary['audit_hash'])}", small))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Generated by CAZO EASM on {_fmt_date(datetime.now(timezone.utc), tz_name)}. Confidential.", small))

    buf = io.BytesIO()
    SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"{label} security report", author="CAZO EASM",
    ).build(story)
    return buf.getvalue()


def clean_recipients(values: List[str]) -> List[str]:
    """Normalize and validate the recipient list. Raises ValueError."""
    from app.services.inventory_alerts import _EMAIL_RE

    cleaned: List[str] = []
    for raw in values or []:
        email = str(raw).strip().lower()
        if not email:
            continue
        if len(email) > 254 or not _EMAIL_RE.match(email) or any(c in email for c in "\r\n,;<>\""):
            raise ValueError(f"'{str(raw)[:80]}' is not a valid email address")
        if email not in cleaned:
            cleaned.append(email)
    if len(cleaned) > MAX_RECIPIENTS:
        raise ValueError(f"At most {MAX_RECIPIENTS} recipients are allowed")
    return cleaned


_manual_sends: Dict[str, List[float]] = {}


def allow_manual_send(organization_id: str, limit: int = 5, window: int = 600) -> bool:
    """At most ``limit`` "send me a copy" emails per organization per ``window`` seconds (per process)."""
    import time

    now = time.monotonic()
    recent = [t for t in _manual_sends.get(organization_id, []) if now - t < window]
    if len(recent) >= limit:
        _manual_sends[organization_id] = recent
        return False
    recent.append(now)
    _manual_sends[organization_id] = recent
    return True


# ── Sending ──────────────────────────────────────────────────────────────


def email_configured() -> bool:
    from app.services.inventory_alerts import email_delivery_status

    return bool(email_delivery_status()["configured"])


def send_report(
    db: Session, schedule: ReportSchedule, *, now: Optional[datetime] = None,
    only_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Build and send one report. ``only_to`` sends a single copy (the "send me a copy" button)."""
    from app.services.email import get_email_service

    now = now or datetime.now(timezone.utc)
    start, end = period_for(schedule.frequency, now)
    summary = build_summary(db, schedule.organization_id, start, end)
    subject, html_body, text_body = render_email(summary, schedule.name, schedule.timezone, schedule.frequency)
    attachments = []
    if schedule.include_pdf:
        filename = f"cazo-security-report-{end.astimezone(get_zone(schedule.timezone)).strftime('%Y-%m-%d')}.pdf"
        attachments.append((filename, render_pdf(summary, schedule.timezone, schedule.frequency), "application/pdf"))

    recipients = [only_to] if only_to else list(schedule.recipients or [])
    if not email_configured():
        return {"status": "not_configured", "sent": 0, "failed": len(recipients),
                "error": "Email sending is not set up on this platform yet."}
    service = get_email_service()
    sent = failed = 0
    for to in recipients:
        try:
            ok = service.send(to=to, subject=subject, html_body=html_body, text_body=text_body,
                              from_name="CAZO EASM", attachments=attachments)
        except Exception:  # noqa: BLE001
            logger.exception("Report email failed for schedule %s", schedule.id)
            ok = False
        sent, failed = sent + (1 if ok else 0), failed + (0 if ok else 1)
    status = "sent" if failed == 0 and sent else ("partial" if sent else "failed")
    error = None if status == "sent" else f"{failed} of {len(recipients)} emails could not be sent."
    return {"status": status, "sent": sent, "failed": failed, "error": error}


def run_due_reports(db: Session, now: Optional[datetime] = None, limit: int = 50) -> int:
    """Send every report whose time has come. Safe to run from several workers."""
    now = now or datetime.now(timezone.utc)
    due = (
        db.query(ReportSchedule)
        .filter(ReportSchedule.enabled.is_(True), ReportSchedule.next_run_at.isnot(None),
                ReportSchedule.next_run_at <= now)
        .order_by(ReportSchedule.next_run_at.asc()).limit(limit).all()
    )
    done = 0
    for schedule in due:
        schedule_id, planned = schedule.id, schedule.next_run_at
        upcoming = compute_next_run(
            schedule.frequency, schedule.weekday, schedule.day_of_month, schedule.hour, schedule.timezone, after=now,
        )
        # Claim it by moving next_run_at forward; only one worker's UPDATE matches.
        claimed = (
            db.query(ReportSchedule)
            .filter(ReportSchedule.id == schedule_id, ReportSchedule.next_run_at == planned,
                    ReportSchedule.enabled.is_(True))
            .update({"next_run_at": upcoming}, synchronize_session=False)
        )
        db.commit()
        if not claimed:
            continue
        schedule = db.query(ReportSchedule).filter(ReportSchedule.id == schedule_id).first()
        try:
            result = send_report(db, schedule, now=now)
        except Exception:  # noqa: BLE001
            logger.exception("Scheduled report %s failed", schedule_id)
            db.rollback()
            schedule = db.query(ReportSchedule).filter(ReportSchedule.id == schedule_id).first()
            result = {"status": "failed", "sent": 0, "failed": 0, "error": "The report could not be generated."}
        schedule.last_run_at = now
        schedule.last_status = result["status"]
        schedule.last_error = (result.get("error") or None) and result["error"][:300]
        db.commit()
        try:
            from app.services.audit import log_event

            log_event(db, action="report_schedule.sent", organization_id=schedule.organization_id,
                      actor_type="system", target_type="report_schedule", target_id=schedule_id,
                      status="success" if result["status"] == "sent" else "failure",
                      detail={"name": schedule.name, "recipients": len(schedule.recipients or []),
                              "sent": result["sent"], "result": result["status"]})
        except Exception:  # noqa: BLE001
            pass
        done += 1
    return done
