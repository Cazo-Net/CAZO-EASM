from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any

from app.blockchain.domain.entities.transaction import Transaction
from app.blockchain.domain.entities.address import Address
from .models import TravelRuleMessage, TravelRuleStatus, ComplianceCase, ComplianceCaseStatus, CARFReport
from .vasp_registry import VASPRegistry

logger = logging.getLogger(__name__)


class TravelRuleService:
    _messages: dict[str, TravelRuleMessage] = {}
    _cases: dict[str, ComplianceCase] = {}
    _reports: dict[str, CARFReport] = {}

    def detect_vasp_interaction(self, tx: Transaction) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        chain = tx.chain.value if hasattr(tx.chain, 'value') else str(tx.chain)

        for addr_field, role in [("from_address", "originator"), ("to_address", "beneficiary")]:
            addr = getattr(tx, addr_field, "")
            if not addr:
                continue
            vasp = VASPRegistry.find_by_address(addr)
            if vasp:
                results.append({
                    "vasp_id": vasp.id,
                    "vasp_name": vasp.name,
                    "address": addr,
                    "role": role,
                    "chain": chain,
                })
        return results

    async def create_travel_rule_case(self, tx: Transaction) -> ComplianceCase | None:
        chain = tx.chain.value if hasattr(tx.chain, 'value') else str(tx.chain)
        interactions = self.detect_vasp_interaction(tx)
        if not interactions:
            return None

        originator_vasp = None
        beneficiary_vasp = None
        for interaction in interactions:
            if interaction["role"] == "originator":
                originator_vasp = interaction["vasp_id"]
            elif interaction["role"] == "beneficiary":
                beneficiary_vasp = interaction["vasp_id"]

        value_str = str(tx.value.to_native().value) if tx.value else "0"
        case_id = str(uuid.uuid4())

        case = ComplianceCase(
            id=case_id,
            tx_hash=tx.hash,
            chain=chain,
            originator_address=tx.from_address or "",
            beneficiary_address=tx.to_address or "",
            value=value_str,
            originator_vasp_id=originator_vasp,
            beneficiary_vasp_id=beneficiary_vasp,
        )
        self._cases[case_id] = case

        tx_msg_id = str(uuid.uuid4())
        originator_vasp_id = originator_vasp or "unknown"
        beneficiary_vasp_id = beneficiary_vasp or "unknown"

        tx_msg = TravelRuleMessage(
            id=tx_msg_id,
            case_id=case_id,
            sender_vasp_id=originator_vasp_id,
            receiver_vasp_id=beneficiary_vasp_id,
            tx_hash=tx.hash,
            chain=chain,
            originator_address=tx.from_address or "",
            beneficiary_address=tx.to_address or "",
            value=value_str,
            status=TravelRuleStatus.PENDING,
            payload=json.dumps({
                "originator": {"address": tx.from_address, "vasp": originator_vasp},
                "beneficiary": {"address": tx.to_address, "vasp": beneficiary_vasp},
                "amount": value_str,
                "asset": chain,
                "timestamp": datetime.utcnow().isoformat(),
            }),
        )
        self._messages[tx_msg_id] = tx_msg

        logger.info("Travel rule case %s created for tx %s", case_id, tx.hash[:16])
        return case

    def list_cases(self, status: str | None = None, limit: int = 50) -> list[dict]:
        results = list(self._cases.values())
        if status:
            results = [c for c in results if c.status.value == status]
        results.sort(key=lambda c: c.created_at, reverse=True)
        return [c.to_dict() for c in results[:limit]]

    def get_case(self, case_id: str) -> dict | None:
        case = self._cases.get(case_id)
        if not case:
            return None
        messages = [m.to_dict() for m in self._messages.values() if m.case_id == case_id]
        return {**case.to_dict(), "messages": messages}

    def get_message(self, msg_id: str) -> dict | None:
        msg = self._messages.get(msg_id)
        return msg.to_dict() if msg else None

    def list_messages(self, status: str | None = None, limit: int = 50) -> list[dict]:
        results = list(self._messages.values())
        if status:
            results = [m for m in results if m.status.value == status]
        results.sort(key=lambda m: m.created_at, reverse=True)
        return [m.to_dict() for m in results[:limit]]

    def acknowledge_message(self, msg_id: str) -> bool:
        msg = self._messages.get(msg_id)
        if msg:
            msg.status = TravelRuleStatus.ACKNOWLEDGED
            msg.acknowledged_at = datetime.utcnow()
            return True
        return False

    def update_case_status(self, case_id: str, status: ComplianceCaseStatus) -> bool:
        case = self._cases.get(case_id)
        if case:
            case.status = status
            case.updated_at = datetime.utcnow()
            if status in (ComplianceCaseStatus.RESOLVED, ComplianceCaseStatus.CLOSED):
                case.resolved_at = datetime.utcnow()
            return True
        return False

    def add_case_note(self, case_id: str, note: str, user: str = "") -> bool:
        case = self._cases.get(case_id)
        if case:
            case.notes.append({
                "note": note,
                "user": user,
                "timestamp": datetime.utcnow().isoformat(),
            })
            case.updated_at = datetime.utcnow()
            return True
        return False

    def generate_carf_report(self, vasp_id: str, year: int, quarter: int) -> CARFReport | None:
        vasp = VASPRegistry.get(vasp_id)
        if not vasp:
            return None

        relevant = [
            m for m in self._messages.values()
            if (m.sender_vasp_id == vasp_id or m.receiver_vasp_id == vasp_id)
        ]

        report_id = str(uuid.uuid4())
        total_value = sum(float(m.value) for m in relevant if m.value)

        report = CARFReport(
            id=report_id,
            year=year,
            quarter=quarter,
            vasp_id=vasp_id,
            jurisdiction=vasp.jurisdiction,
            total_transactions=len(relevant),
            total_value=str(total_value),
            transactions=[m.to_dict() for m in relevant],
        )
        self._reports[report_id] = report
        return report

    def list_reports(self, vasp_id: str | None = None) -> list[dict]:
        results = list(self._reports.values())
        if vasp_id:
            results = [r for r in results if r.vasp_id == vasp_id]
        return [r.to_dict() for r in sorted(results, key=lambda r: (r.year, r.quarter), reverse=True)]

    def confirm_report_filed(self, report_id: str) -> bool:
        report = self._reports.get(report_id)
        if report:
            report.filed = True
            return True
        return False

    def stats(self) -> dict[str, Any]:
        return {
            "total_cases": len(self._cases),
            "open_cases": sum(1 for c in self._cases.values() if c.status == ComplianceCaseStatus.OPEN),
            "resolved_cases": sum(1 for c in self._cases.values() if c.status == ComplianceCaseStatus.RESOLVED),
            "pending_messages": sum(1 for m in self._messages.values() if m.status == TravelRuleStatus.PENDING),
            "sent_messages": sum(1 for m in self._messages.values() if m.status == TravelRuleStatus.SENT),
            "total_reports": len(self._reports),
        }


travel_rule_service = TravelRuleService()
