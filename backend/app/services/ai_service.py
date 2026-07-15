from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
import json
import logging
import time

from app.models.ai import AIConversation, AIMessage, AIRecommendation, AIUsageLog, AISettings, AIKnowledgeArticle
from app.services.ai_provider import get_ai_provider
from app.services.ai_context import ContextBuilder
from app.services.ai_prompts import PromptBuilder
from app.models.organization import Organization
from app.models.project import Project

logger = logging.getLogger(__name__)


class AIService:
    """Main AI service orchestrating all AI operations."""

    def __init__(self, db: Session):
        self.db = db
        self.context_builder = ContextBuilder(db)
        self.prompt_builder = PromptBuilder()
        self.provider = get_ai_provider()

    def _get_settings(self, user_id: str) -> Optional[AISettings]:
        return self.db.query(AISettings).filter(AISettings.user_id == user_id).first()

    def _ensure_settings(self, user_id: str) -> AISettings:
        settings = self._get_settings(user_id)
        if not settings:
            settings = AISettings(user_id=user_id)
            self.db.add(settings)
            self.db.commit()
            self.db.refresh(settings)
        return settings

    def _log_usage(self, user_id: str, action: str, model: str, tokens: int, response_time_ms: int, org_id: str = None):
        log = AIUsageLog(
            user_id=user_id,
            action=action,
            model_used=model,
            tokens_used=tokens,
            response_time_ms=response_time_ms,
            org_id=org_id,
        )
        self.db.add(log)
        self.db.commit()

    async def chat(
        self,
        user_id: str,
        conversation_id: Optional[str],
        message: str,
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        settings = self._ensure_settings(user_id)

        if conversation_id:
            conv = self.db.query(AIConversation).filter(
                AIConversation.id == conversation_id,
                AIConversation.user_id == user_id,
            ).first()
        else:
            conv = AIConversation(
                user_id=user_id,
                title=message[:80],
                context_org_id=org_id,
                context_project_id=project_id,
            )
            self.db.add(conv)
            self.db.commit()
            self.db.refresh(conv)

        user_msg = AIMessage(
            conversation_id=conv.id,
            role="user",
            content=message,
        )
        self.db.add(user_msg)
        self.db.commit()

        org_name = None
        if org_id:
            org = self.db.query(Organization).filter(Organization.id == org_id).first()
            org_name = org.name if org else None
        project_name = None
        if project_id:
            proj = self.db.query(Project).filter(Project.id == project_id).first()
            project_name = proj.name if proj else None

        context = self.context_builder.build_full_context(user_id, org_id, project_id)
        context_summary = self.context_builder.build_summary(context)

        system_prompt = self.prompt_builder.build_system_prompt(
            context_summary=context_summary,
            tone=settings.tone,
            org_name=org_name,
            project_name=project_name,
        )

        history_msgs = self.db.query(AIMessage).filter(
            AIMessage.conversation_id == conv.id,
            AIMessage.role.in_(["user", "assistant"]),
        ).order_by(AIMessage.created_at).all()
        history = [{"role": m.role, "content": m.content} for m in history_msgs[:-1]]

        messages = self.prompt_builder.build_chat_messages(
            system_prompt=system_prompt,
            history=history,
            user_message=message,
        )

        start = time.time()
        try:
            result = await self.provider.complete(messages)
            elapsed_ms = int((time.time() - start) * 1000)

            assistant_msg = AIMessage(
                conversation_id=conv.id,
                role="assistant",
                content=result["content"],
                token_count=result.get("tokens", 0),
                model_used=result.get("model", "unknown"),
                response_time_ms=elapsed_ms,
            )
            self.db.add(assistant_msg)
            self.db.commit()
            self.db.refresh(assistant_msg)

            self._log_usage(user_id, "chat", result.get("model", "unknown"), result.get("tokens", 0), elapsed_ms, org_id)

            suggestions = self._generate_suggestions(message, result["content"], context)
            references = self._extract_references(result["content"], context)

            return {
                "conversation_id": conv.id,
                "message": {
                    "id": assistant_msg.id,
                    "role": "assistant",
                    "content": result["content"],
                    "token_count": result.get("tokens", 0),
                    "model_used": result.get("model", "unknown"),
                    "response_time_ms": elapsed_ms,
                    "created_at": assistant_msg.created_at.isoformat(),
                },
                "suggestions": suggestions,
                "references": references,
            }

        except Exception as e:
            logger.error(f"AI chat error: {e}")
            elapsed_ms = int((time.time() - start) * 1000)
            error_msg = AIMessage(
                conversation_id=conv.id,
                role="assistant",
                content=json.dumps({
                    "summary": "I encountered an error processing your request.",
                    "error": str(e),
                    "recommendations": ["Please try again or rephrase your question."]
                }),
                model_used="error",
                response_time_ms=elapsed_ms,
            )
            self.db.add(error_msg)
            self.db.commit()
            self.db.refresh(error_msg)
            return {
                "conversation_id": conv.id,
                "message": {
                    "id": error_msg.id,
                    "role": "assistant",
                    "content": error_msg.content,
                    "token_count": 0,
                    "model_used": "error",
                    "response_time_ms": elapsed_ms,
                    "created_at": error_msg.created_at.isoformat(),
                },
                "suggestions": [],
                "references": [],
            }

    def _generate_suggestions(self, user_msg: str, ai_response: str, context: Dict) -> List[str]:
        suggestions = []
        if "certificate" in user_msg.lower() or "ssl" in user_msg.lower():
            suggestions.append("Show certificates expiring this month")
            suggestions.append("What are the best practices for certificate management?")
        elif "vulnerability" in user_msg.lower() or "vuln" in user_msg.lower():
            suggestions.append("Show critical vulnerabilities")
            suggestions.append("What is the mean time to remediate?")
        elif "scan" in user_msg.lower():
            suggestions.append("Show recent scan results")
            suggestions.append("Compare scan results from last week")
        else:
            suggestions.append("Summarize my platform status")
            suggestions.append("What changed today?")
            suggestions.append("Show top recommendations")
        return suggestions[:3]

    def _extract_references(self, content: str, context: Dict) -> List[Dict[str, Any]]:
        refs = []
        if "scans" in context:
            for scan in context["scans"].get("recent", [])[:3]:
                refs.append({"type": "scan", "id": scan["id"], "label": scan["domain"]})
        return refs[:5]

    async def search(self, user_id: str, query: str, org_id: str = None, project_id: str = None) -> Dict[str, Any]:
        settings = self._ensure_settings(user_id)
        context = self.context_builder.build_full_context(user_id, org_id, project_id)
        context_summary = self.context_builder.build_summary(context)

        search_prompt = self.prompt_builder.build_search_prompt(query, context_summary, context)
        messages = [
            {"role": "system", "content": "You are a search query parser. Parse natural language queries into structured filters. Respond with JSON only."},
            {"role": "user", "content": search_prompt},
        ]

        start = time.time()
        result = await self.provider.complete(messages, max_tokens=1024)
        elapsed_ms = int((time.time() - start) * 1000)

        try:
            parsed = json.loads(result["content"])
        except json.JSONDecodeError:
            parsed = {"interpretation": query, "filters": {}, "entity_type": "subdomains"}

        self._log_usage(user_id, "search", result.get("model", "unknown"), result.get("tokens", 0), elapsed_ms, org_id)

        return {
            "query": query,
            "interpretation": parsed.get("interpretation", query),
            "results": [],
            "filters_applied": parsed.get("filters", {}),
            "count": 0,
        }

    async def generate_report(
        self,
        user_id: str,
        report_type: str,
        org_id: str = None,
        project_id: str = None,
        date_from: str = None,
        date_to: str = None,
    ) -> Dict[str, Any]:
        settings = self._ensure_settings(user_id)
        context = self.context_builder.build_full_context(user_id, org_id, project_id)

        date_range = None
        if date_from or date_to:
            date_range = f"{date_from or 'start'} to {date_to or 'now'}"

        prompt = self.prompt_builder.build_report_prompt(report_type, context, date_range)
        messages = [
            {"role": "system", "content": "You are a report generator. Generate comprehensive security reports in Markdown format."},
            {"role": "user", "content": prompt},
        ]

        start = time.time()
        result = await self.provider.complete(messages, max_tokens=4096)
        elapsed_ms = int((time.time() - start) * 1000)

        self._log_usage(user_id, "report", result.get("model", "unknown"), result.get("tokens", 0), elapsed_ms, org_id)

        return {
            "id": f"rpt_{int(time.time())}",
            "title": f"{report_type.replace('_', ' ').title()} Report",
            "content": result["content"],
            "report_type": report_type,
            "format": "markdown",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_recommendations(self, user_id: str, org_id: str = None, project_id: str = None) -> List[Dict[str, Any]]:
        existing = self.db.query(AIRecommendation).filter(
            AIRecommendation.user_id == user_id,
            AIRecommendation.dismissed == False,
        ).order_by(AIRecommendation.created_at.desc()).limit(20).all()

        if existing:
            return [
                {
                    "id": r.id,
                    "category": r.category,
                    "title": r.title,
                    "description": r.description,
                    "priority": r.priority,
                    "entity_type": r.entity_type,
                    "entity_id": r.entity_id,
                    "status": r.status,
                    "created_at": r.created_at.isoformat(),
                }
                for r in existing
            ]

        context = self.context_builder.build_full_context(user_id, org_id, project_id)
        settings = self._ensure_settings(user_id)

        prompt = self.prompt_builder.build_recommendations_prompt(context)
        messages = [
            {"role": "system", "content": "You are a recommendation engine. Generate security recommendations based on platform data. Respond with JSON."},
            {"role": "user", "content": prompt},
        ]

        start = time.time()
        result = await self.provider.complete(messages, max_tokens=2048)
        elapsed_ms = int((time.time() - start) * 1000)

        self._log_usage(user_id, "recommendations", result.get("model", "unknown"), result.get("tokens", 0), elapsed_ms, org_id)

        try:
            data = json.loads(result["content"])
            recs = data if isinstance(data, list) else data.get("recommendations", [])
        except json.JSONDecodeError:
            recs = []

        saved = []
        for rec in recs[:10]:
            r = AIRecommendation(
                user_id=user_id,
                org_id=org_id,
                project_id=project_id,
                category=rec.get("category", "general"),
                title=rec.get("title", ""),
                description=rec.get("description", ""),
                priority=rec.get("priority", "medium"),
            )
            self.db.add(r)
            saved.append({
                "id": r.id,
                "category": r.category,
                "title": r.title,
                "description": r.description,
                "priority": r.priority,
                "status": r.status,
            })

        self.db.commit()
        return saved

    def get_dashboard(self, user_id: str, org_id: str = None) -> Dict[str, Any]:
        context = self.context_builder.build_full_context(user_id, org_id)
        recs = self.db.query(AIRecommendation).filter(
            AIRecommendation.user_id == user_id,
            AIRecommendation.dismissed == False,
        ).order_by(AIRecommendation.created_at.desc()).limit(5).all()

        return {
            "today_summary": {
                "scans": context["scans"]["total"],
                "subdomains": context["subdomains"]["total"],
                "vulnerabilities": context["vulnerabilities"]["total"],
                "risk_score": context["risk"]["latest_score"],
            },
            "recent_changes": context["scans"]["recent"][:5],
            "recommendations": [
                {"id": r.id, "title": r.title, "priority": r.priority, "category": r.category}
                for r in recs
            ],
            "certificate_alerts": {
                "expiring_soon": context["ssl_certificates"]["expiring_soon"],
                "expired": context["ssl_certificates"]["expired"],
            },
            "technology_changes": {
                "unique": context["technologies"]["unique"],
                "total": context["technologies"]["total"],
            },
            "platform_health": {
                "total_assets": context["subdomains"]["total"] + context["ports"]["total"] + context["ssl_certificates"]["total"],
                "alive_percentage": round(context["subdomains"]["alive"] / max(context["subdomains"]["total"], 1) * 100),
            },
        }

    def get_usage_stats(self, user_id: str) -> Dict[str, Any]:
        logs = self.db.query(AIUsageLog).filter(AIUsageLog.user_id == user_id).all()
        total_questions = sum(1 for l in logs if l.action == "chat")
        total_reports = sum(1 for l in logs if l.action == "report")
        avg_time = sum(l.response_time_ms for l in logs) / max(len(logs), 1)
        total_tokens = sum(l.tokens_used for l in logs)
        estimated_cost = total_tokens * 0.000002

        return {
            "total_questions": total_questions,
            "total_reports": total_reports,
            "avg_response_time_ms": int(avg_time),
            "total_tokens": total_tokens,
            "estimated_cost": round(estimated_cost, 4),
        }
