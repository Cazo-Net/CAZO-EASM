"""Blockchain case management.

CRUD for investigation cases, annotations, member assignments,
and audit trail.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.blockchain import (
    CaseAnnotation,
    CaseAuditEntry,
    CaseMember,
    CaseMemberRole,
    CaseRecord,
    CaseStatus,
)

logger = logging.getLogger(__name__)

# In-memory store for demo; production would use a database
_cases: dict[str, CaseRecord] = {}
_annotations: dict[str, list[CaseAnnotation]] = {}
_members: dict[str, list[CaseMember]] = {}
_audit: dict[str, list[CaseAuditEntry]] = {}


# ── Case CRUD ────────────────────────────────────────────────────────────────

def create_case(
    org_id: str,
    title: str,
    created_by: str,
    description: str = "",
    assigned_to: str | None = None,
) -> CaseRecord:
    """Create a new investigation case."""
    case_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    case = CaseRecord(
        id=case_id,
        org_id=org_id,
        title=title,
        description=description,
        status=CaseStatus.OPEN,
        created_by=created_by,
        assigned_to=assigned_to,
        created_at=now,
        updated_at=now,
    )
    _cases[case_id] = case
    _annotations[case_id] = []
    _members[case_id] = [
        CaseMember(case_id=case_id, user_id=created_by, role=CaseMemberRole.OWNER)
    ]
    _audit[case_id] = [
        CaseAuditEntry(
            case_id=case_id,
            user_id=created_by,
            action="created",
            detail={"title": title},
        )
    ]
    return case


def get_case(case_id: str) -> CaseRecord | None:
    return _cases.get(case_id)


def list_cases(
    org_id: str | None = None,
    status: CaseStatus | None = None,
    assigned_to: str | None = None,
) -> list[CaseRecord]:
    """List cases with optional filters."""
    results = list(_cases.values())
    if org_id:
        results = [c for c in results if c.org_id == org_id]
    if status:
        results = [c for c in results if c.status == status]
    if assigned_to:
        results = [c for c in results if c.assigned_to == assigned_to]
    return sorted(results, key=lambda c: c.updated_at, reverse=True)


def update_case(
    case_id: str,
    user_id: str,
    title: str | None = None,
    description: str | None = None,
    status: CaseStatus | None = None,
    assigned_to: str | None = None,
) -> CaseRecord | None:
    """Update a case and record audit entry."""
    case = _cases.get(case_id)
    if not case:
        return None

    changes: dict[str, Any] = {}
    if title is not None:
        case.title = title
        changes["title"] = title
    if description is not None:
        case.description = description
        changes["description"] = description
    if status is not None:
        old_status = case.status
        case.status = status
        changes["status"] = {"from": old_status.value, "to": status.value}
    if assigned_to is not None:
        case.assigned_to = assigned_to
        changes["assigned_to"] = assigned_to

    case.updated_at = datetime.now(timezone.utc)

    if changes:
        _audit.setdefault(case_id, []).append(CaseAuditEntry(
            case_id=case_id,
            user_id=user_id,
            action="updated",
            detail=changes,
        ))

    return case


def delete_case(case_id: str) -> bool:
    """Delete a case and all associated data."""
    if case_id in _cases:
        del _cases[case_id]
        _annotations.pop(case_id, None)
        _members.pop(case_id, None)
        _audit.pop(case_id, None)
        return True
    return False


# ── Annotations ──────────────────────────────────────────────────────────────

def add_annotation(
    case_id: str,
    user_id: str,
    content: str,
    entity_type: str = "address",
    entity_id: str = "",
) -> CaseAnnotation | None:
    """Add an annotation to a case."""
    if case_id not in _cases:
        return None

    ann_id = str(uuid.uuid4())
    ann = CaseAnnotation(
        id=ann_id,
        case_id=case_id,
        entity_type=entity_type,
        entity_id=entity_id,
        content=content,
        author_id=user_id,
    )
    _annotations.setdefault(case_id, []).append(ann)

    _audit.setdefault(case_id, []).append(CaseAuditEntry(
        case_id=case_id,
        user_id=user_id,
        action="annotated",
        detail={"entity_type": entity_type, "entity_id": entity_id},
    ))

    # Update case timestamp
    case = _cases[case_id]
    case.updated_at = datetime.now(timezone.utc)

    return ann


def list_annotations(case_id: str) -> list[CaseAnnotation]:
    """List annotations for a case."""
    return _annotations.get(case_id, [])


def delete_annotation(case_id: str, annotation_id: str) -> bool:
    """Delete an annotation."""
    anns = _annotations.get(case_id, [])
    for i, ann in enumerate(anns):
        if ann.id == annotation_id:
            anns.pop(i)
            return True
    return False


# ── Members ──────────────────────────────────────────────────────────────────

def add_member(
    case_id: str,
    user_id: str,
    role: CaseMemberRole = CaseMemberRole.ANALYST,
    added_by: str | None = None,
) -> CaseMember | None:
    """Add a member to a case."""
    if case_id not in _cases:
        return None

    member = CaseMember(
        case_id=case_id,
        user_id=user_id,
        role=role,
        added_by=added_by,
    )
    _members.setdefault(case_id, []).append(member)

    _audit.setdefault(case_id, []).append(CaseAuditEntry(
        case_id=case_id,
        user_id=added_by or "system",
        action="member_added",
        detail={"user_id": user_id, "role": role.value},
    ))

    return member


def list_members(case_id: str) -> list[CaseMember]:
    """List members of a case."""
    return _members.get(case_id, [])


def remove_member(case_id: str, user_id: str) -> bool:
    """Remove a member from a case."""
    members = _members.get(case_id, [])
    for i, m in enumerate(members):
        if m.user_id == user_id:
            members.pop(i)
            return True
    return False


def update_member_role(
    case_id: str, user_id: str, new_role: CaseMemberRole
) -> bool:
    """Update a member's role."""
    members = _members.get(case_id, [])
    for m in members:
        if m.user_id == user_id:
            m.role = new_role
            return True
    return False


# ── Audit Trail ──────────────────────────────────────────────────────────────

def get_audit_trail(case_id: str) -> list[CaseAuditEntry]:
    """Get the audit trail for a case."""
    return _audit.get(case_id, [])


# ── Stats ────────────────────────────────────────────────────────────────────

def case_stats(org_id: str) -> dict[str, Any]:
    """Get case statistics for an organization."""
    org_cases = [c for c in _cases.values() if c.org_id == org_id]
    return {
        "total": len(org_cases),
        "open": sum(1 for c in org_cases if c.status == CaseStatus.OPEN),
        "in_review": sum(1 for c in org_cases if c.status == CaseStatus.IN_REVIEW),
        "closed": sum(1 for c in org_cases if c.status == CaseStatus.CLOSED),
    }
