"""Integration status API.

Provides visibility into which third-party integrations are configured.
"""
from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

# Environment variables for each integration
INTEGRATION_ENV_MAP: Dict[str, Dict[str, Any]] = {
    "splunk": {
        "env_var": "SPLUNK_HEC_URL",
        "preview_var": "SPLUNK_HEC_URL",
    },
    "elastic": {
        "env_var": "ELASTIC_URL",
        "preview_var": "ELASTIC_URL",
    },
    "sentinel": {
        "env_var": "SENTINEL_WORKSPACE_ID",
        "preview_var": "SENTINEL_WORKSPACE_ID",
    },
    "jira": {
        "env_var": "JIRA_URL",
        "preview_var": "JIRA_URL",
    },
    "slack": {
        "env_var": "SLACK_WEBHOOK_URL",
        "preview_var": "SLACK_WEBHOOK_URL",
    },
    "teams": {
        "env_var": "TEAMS_WEBHOOK_URL",
        "preview_var": "TEAMS_WEBHOOK_URL",
    },
}


def _mask_value(value: str) -> str:
    """Mask sensitive values, showing only first/last few chars."""
    if len(value) <= 8:
        return "****"
    return value[:4] + "****" + value[-4:]


@router.get("/status")
async def get_integration_status(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get configuration status of all integrations."""
    configured: Dict[str, bool] = {}
    previews: Dict[str, str] = {}

    for name, env_info in INTEGRATION_ENV_MAP.items():
        env_var = env_info["env_var"]
        value = os.environ.get(env_var, "").strip()
        configured[env_var] = bool(value)
        if value:
            previews[env_var] = _mask_value(value)

    return {
        "configured": configured,
        "previews": previews,
    }
