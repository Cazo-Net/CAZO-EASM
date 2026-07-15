from typing import Dict, Any, List, Optional
import json


class PromptBuilder:
    """Builds structured prompts for the AI provider."""

    SYSTEM_BASE = """You are AttackSec AI, an intelligent cybersecurity assistant integrated into the AttackSec platform.

Your role is to help users understand, analyze, and manage their external attack surface. You have access to the user's platform data and can provide insights, summaries, recommendations, and explanations.

IMPORTANT RULES:
1. Only use data provided in the context. Never fabricate data.
2. Be concise but thorough. Use structured JSON responses when appropriate.
3. Always link insights to specific platform data when possible.
4. Recommend actions but never execute them autonomously.
5. Respect organization and project boundaries.
6. Clearly identify AI-generated content.
7. When uncertain, say so. Do not guess.

When the user asks a question, respond with structured JSON containing:
- summary: A clear summary of findings
- key_observations: List of important observations
- recommendations: List of actionable recommendations
- references: Links to related platform entities (scans, assets, etc.)
- suggested_questions: Follow-up questions the user might ask"""

    TONE_MAP = {
        "executive": "Respond in an executive tone. Focus on business impact, risk posture, and high-level strategy. Use clear, professional language suitable for C-suite communication.",
        "technical": "Respond in a technical tone. Provide detailed technical analysis, specific metrics, and actionable technical recommendations. Use precise terminology.",
        "balanced": "Respond in a balanced tone. Mix strategic overview with technical detail as appropriate for the question.",
    }

    def build_system_prompt(
        self,
        context_summary: str,
        tone: str = "balanced",
        org_name: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> str:
        parts = [self.SYSTEM_BASE]
        parts.append(f"\nTONE: {self.TONE_MAP.get(tone, self.TONE_MAP['balanced'])}")
        if org_name:
            parts.append(f"\nORGANIZATION: {org_name}")
        if project_name:
            parts.append(f"\nPROJECT: {project_name}")
        parts.append(f"\nCURRENT PLATFORM DATA:\n{context_summary}")
        return "\n".join(parts)

    def build_chat_messages(
        self,
        system_prompt: str,
        history: List[Dict[str, str]],
        user_message: str,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history[-20:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        if additional_context:
            ctx_str = f"\n\n[Additional context]\n{json.dumps(additional_context, indent=2, default=str)}"
            user_message = user_message + ctx_str
        messages.append({"role": "user", "content": user_message})
        return messages

    def build_search_prompt(self, query: str, context_summary: str, available_data: Dict[str, Any]) -> str:
        return f"""Parse the following natural language query and convert it to structured search filters.

Query: "{query}"

Available data types:
- subdomains (hostname, ip_addresses, is_alive, status)
- ports (port_number, state, service, version, status)
- ssl_certificates (hostname, issuer, is_valid, grade, not_after, status)
- technologies (name, category, version, confidence, status)
- dns_records (record_type, value, ttl, status)
- vulnerabilities (severity, name, host, vuln_type)
- reports (title, report_type, created_at)
- scans (domain, status, scan_type, created_at)

Respond with JSON containing:
- interpretation: Plain English interpretation of the query
- filters: Structured filter object
- entity_type: Primary entity type to search
- date_range: If applicable"""

    def build_summary_prompt(self, data_type: str, data: Any, context: Dict[str, Any]) -> str:
        return f"""Summarize the following {data_type} data from the AttackSec platform.

Data:
{json.dumps(data, indent=2, default=str)}

Context:
{json.dumps(context, indent=2, default=str)}

Provide a clear, actionable summary with key observations and recommendations."""

    def build_report_prompt(self, report_type: str, context: Dict[str, Any], date_range: Optional[str] = None) -> str:
        return f"""Generate a {report_type} report for the AttackSec platform.

Platform Context:
{json.dumps(context, indent=2, default=str)}

{f'Date Range: {date_range}' if date_range else ''}

Generate a comprehensive {report_type} report with:
1. Executive Summary
2. Key Findings
3. Detailed Analysis
4. Recommendations
5. Appendix with data tables if applicable

Use Markdown formatting. Be specific with numbers and data points from the context."""

    def build_recommendations_prompt(self, context: Dict[str, Any]) -> str:
        return f"""Based on the following platform data, generate security recommendations.

Platform Data:
{json.dumps(context, indent=2, default=str)}

Analyze the data and provide:
1. Critical recommendations requiring immediate attention
2. Important recommendations for improving security posture
3. Nice-to-have improvements

For each recommendation, provide:
- title: Short description
- description: Detailed explanation
- priority: critical/high/medium/low
- category: The area it relates to
- rationale: Why this is recommended based on the data"""
