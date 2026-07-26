"""Cloud storage bucket discovery scanner.

Passively detects publicly accessible cloud storage buckets by probing
known endpoint patterns for AWS S3, Azure Blob Storage, and Google Cloud Storage.

This is a passive scanner — it sends HTTP HEAD/GET requests to well-known
storage endpoints and interprets status codes. It does NOT brute-force
bucket names or attempt authentication.
"""
from __future__ import annotations

import asyncio
import re
import logging
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote

import httpx

from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerPriority
from app.scanners.v2.registry import register_scanner, ScannerCategory

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cloud storage endpoint patterns
# ---------------------------------------------------------------------------

# Common subdomain prefixes that often host cloud storage
_BUCKET_PREFIXES = [
    "assets", "static", "media", "images", "img", "files", "uploads",
    "downloads", "backup", "backups", "data", "storage", "cdn", "content",
    "resources", "public", "private", "docs", "dist", "build", "release",
    "releases", "artifacts", "packages", "vendor", "deps", "temp", "tmp",
    "archive", "logs", "exports", "reports",
]

# S3 bucket URL patterns to probe
_S3_ENDPOINTS = [
    # Virtual-hosted style
    "https://{bucket}.s3.amazonaws.com",
    "https://{bucket}.s3.{region}.amazonaws.com",
    # Path style (deprecated but still works)
    "https://s3.amazonaws.com/{bucket}",
    "https://s3.{region}.amazonaws.com/{bucket}",
]

# Azure Blob Storage patterns
_AZURE_ENDPOINTS = [
    "https://{account}.blob.core.windows.net",
    "https://{account}.blob.core.windows.net/?restype=container&comp=list",
]

# Google Cloud Storage patterns
_GCS_ENDPOINTS = [
    "https://storage.googleapis.com/{bucket}",
    "https://{bucket}.storage.googleapis.com",
]

# Regions for S3 probing (common ones)
_S3_REGIONS = ["us-east-1", "us-west-2", "eu-west-1", "eu-central-1", "ap-southeast-1"]

# Status codes that indicate a public bucket
_PUBLIC_INDICATORS = {
    200,  # Direct listing or object access
    403,  # Access denied but bucket exists (partial info leak)
}

# Specific response patterns that confirm exposure
_EXPOSURE_PATTERNS = {
    "s3_list": re.compile(r"<ListBucketResult|<Contents>|<Key>", re.IGNORECASE),
    "azure_list": re.compile(r"<EnumerationResults|<Blob>", re.IGNORECASE),
    "gcs_list": re.compile(r"<ListBucketResult|<Contents>|<Key>", re.IGNORECASE),
    "xml_error": re.compile(r"<Error><Code>(AccessDenied|AllAccessDisabled)</Code>", re.IGNORECASE),
}


def _build_bucket_names(domain: str) -> Set[str]:
    """Generate candidate bucket names from domain."""
    base = domain.split(".")[0]
    names = {base, domain.replace(".", "-"), domain.replace(".", "")}
    for prefix in _BUCKET_PREFIXES:
        names.add(f"{prefix}-{base}")
        names.add(f"{base}-{prefix}")
        names.add(f"{prefix}.{domain}")
    return names


async def _probe_s3(
    bucket: str, client: httpx.AsyncClient, semaphore: asyncio.Semaphore
) -> Optional[Dict[str, Any]]:
    """Probe S3 bucket endpoints for public access."""
    async with semaphore:
        for endpoint_tpl in _S3_ENDPOINTS:
            url = endpoint_tpl.replace("{bucket}", bucket).replace("{region}", "us-east-1")
            try:
                resp = await client.get(url, follow_redirects=True)
                if resp.status_code in _PUBLIC_INDICATORS:
                    body = resp.text[:5000]
                    is_listing = bool(_EXPOSURE_PATTERNS["s3_list"].search(body))
                    is_denied = bool(_EXPOSURE_PATTERNS["xml_error"].search(body))
                    return {
                        "provider": "aws_s3",
                        "bucket": bucket,
                        "url": url,
                        "status_code": resp.status_code,
                        "is_listing": is_listing,
                        "is_denied": is_denied,
                        "exists": True,
                        "severity": "high" if is_listing else "medium",
                    }
            except (httpx.RequestError, httpx.TimeoutException):
                continue
    return None


async def _probe_azure(
    account: str, client: httpx.AsyncClient, semaphore: asyncio.Semaphore
) -> Optional[Dict[str, Any]]:
    """Probe Azure Blob Storage endpoints."""
    async with semaphore:
        for endpoint_tpl in _AZURE_ENDPOINTS:
            url = endpoint_tpl.replace("{account}", account)
            try:
                resp = await client.get(url, follow_redirects=True)
                if resp.status_code in _PUBLIC_INDICATORS:
                    body = resp.text[:5000]
                    is_listing = bool(_EXPOSURE_PATTERNS["azure_list"].search(body))
                    return {
                        "provider": "azure_blob",
                        "account": account,
                        "url": url,
                        "status_code": resp.status_code,
                        "is_listing": is_listing,
                        "is_denied": bool(_EXPOSURE_PATTERNS["xml_error"].search(body)),
                        "exists": True,
                        "severity": "high" if is_listing else "medium",
                    }
            except (httpx.RequestError, httpx.TimeoutException):
                continue
    return None


async def _probe_gcs(
    bucket: str, client: httpx.AsyncClient, semaphore: asyncio.Semaphore
) -> Optional[Dict[str, Any]]:
    """Probe Google Cloud Storage endpoints."""
    async with semaphore:
        for endpoint_tpl in _GCS_ENDPOINTS:
            url = endpoint_tpl.replace("{bucket}", bucket)
            try:
                resp = await client.get(url, follow_redirects=True)
                if resp.status_code in _PUBLIC_INDICATORS:
                    body = resp.text[:5000]
                    is_listing = bool(_EXPOSURE_PATTERNS["gcs_list"].search(body))
                    return {
                        "provider": "gcp_gcs",
                        "bucket": bucket,
                        "url": url,
                        "status_code": resp.status_code,
                        "is_listing": is_listing,
                        "is_denied": bool(_EXPOSURE_PATTERNS["xml_error"].search(body)),
                        "exists": True,
                        "severity": "high" if is_listing else "medium",
                    }
            except (httpx.RequestError, httpx.TimeoutException):
                continue
    return None


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

@register_scanner(
    name="cloud_buckets",
    category=ScannerCategory.VULNERABILITY_ASSESSMENT,
    version="1.0.0",
    enabled=True,
    description="Discover publicly accessible cloud storage buckets (S3, Azure Blob, GCS)",
    priority=ScannerPriority.LOW,
    dependencies=["asset_discovery"],
    capabilities=["cloud_storage_discovery", "s3_bucket_detection", "azure_blob_detection", "gcs_bucket_detection"],
)
class CloudBucketScanner(EnhancedBaseScanner):
    """Detect publicly accessible cloud storage buckets.

    Probes known endpoint patterns for S3, Azure Blob Storage, and GCS
    using candidate bucket names derived from the target domain.
    """

    name = "cloud_buckets"
    version = "1.0.0"
    category = ScannerCategory.VULNERABILITY_ASSESSMENT
    priority = ScannerPriority.LOW
    description = "Discover publicly accessible cloud storage buckets (S3, Azure Blob, GCS)"
    dependencies = ["asset_discovery"]
    capabilities = [
        "cloud_storage_discovery",
        "s3_bucket_detection",
        "azure_blob_detection",
        "gcs_bucket_detection",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.timeout = self.config.get("timeout", 60)
        self._max_concurrent = self.config.get("max_concurrent", 20)

    def validate_target(self, target: str) -> bool:
        return bool(target and "." in target)

    async def scan(self, target: str, **kwargs) -> ScanResult:
        """Probe cloud storage endpoints for the target domain."""
        domain = target.strip().lower()
        bucket_names = _build_bucket_names(domain)
        semaphore = asyncio.Semaphore(self._max_concurrent)

        found: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "CAZO-EASM/1.0 (Security Scanner)"},
        ) as client:
            # Run all probes concurrently
            tasks = []
            for name in bucket_names:
                tasks.append(_probe_s3(name, client, semaphore))
                tasks.append(_probe_azure(name, client, semaphore))
                tasks.append(_probe_gcs(name, client, semaphore))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for r in results:
                if isinstance(r, dict):
                    found.append(r)

        # Deduplicate by URL
        seen_urls: Set[str] = set()
        unique: List[Dict[str, Any]] = []
        for item in found:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                unique.append(item)

        return ScanResult(
            success=True,
            scanner=self.name,
            target=domain,
            data={
                "buckets": unique,
                "total_probed": len(bucket_names) * 3 * len(_S3_ENDPOINTS),
                "total_found": len(unique),
                "providers": {
                    "aws_s3": sum(1 for b in unique if b["provider"] == "aws_s3"),
                    "azure_blob": sum(1 for b in unique if b["provider"] == "azure_blob"),
                    "gcp_gcs": sum(1 for b in unique if b["provider"] == "gcp_gcs"),
                },
            },
        )
