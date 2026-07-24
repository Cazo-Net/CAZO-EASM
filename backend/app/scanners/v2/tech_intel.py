"""Technology intelligence engine with expanded fingerprint database.

Detects:
- Web servers, CDNs, WAFs
- Programming languages and frameworks
- CMS platforms
- JavaScript libraries and frameworks
- Analytics and tracking
- Databases
- Cloud providers
- DevOps tools
"""
from __future__ import annotations

import re
import logging
from typing import Any, Dict, List

import httpx

from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerPriority
from app.scanners.v2.registry import register_scanner, ScannerCategory

logger = logging.getLogger(__name__)

# Expanded fingerprint database: name → {category, patterns: {header, cookie, html, meta}}
FINGERPRINTS: Dict[str, Dict[str, Any]] = {
    # Web Servers
    "nginx": {"category": "Web Server", "patterns": {"header": [r"nginx"]}},
    "apache": {"category": "Web Server", "patterns": {"header": [r"apache"]}},
    "iis": {"category": "Web Server", "patterns": {"header": [r"microsoft-iis"]}},
    "lighttpd": {"category": "Web Server", "patterns": {"header": [r"lighttpd"]}},
    "caddy": {"category": "Web Server", "patterns": {"header": [r"caddy"]}},
    "openresty": {"category": "Web Server", "patterns": {"header": [r"openresty"]}},
    "litespeed": {"category": "Web Server", "patterns": {"header": [r"litespeed"]}},
    "envoy": {"category": "Web Server", "patterns": {"header": [r"envoy"]}},
    "traefik": {"category": "Web Server", "patterns": {"header": [r"traefik"]}},

    # CDNs
    "cloudflare": {"category": "CDN", "patterns": {"header": [r"cloudflare"]}},
    "akamai": {"category": "CDN", "patterns": {"header": [r"akamaighost"]}},
    "fastly": {"category": "CDN", "patterns": {"header": [r"fastly"]}},
    "aws_cloudfront": {"category": "CDN", "patterns": {"header": [r"cloudfront"]}},
    "azure_cdn": {"category": "CDN", "patterns": {"header": [r"azureedge"]}},
    "cloudflare_cdn": {"category": "CDN", "patterns": {"header": [r"cf-ray"]}},

    # WAFs
    "cloudflare_waf": {"category": "WAF", "patterns": {"header": [r"cf-cache-status"]}},
    "akamai_waf": {"category": "WAF", "patterns": {"header": [r"akamai"]}},
    "aws_waf": {"category": "WAF", "patterns": {"header": [r"x-amzn-requestid"]}},
    "incapsula": {"category": "WAF", "patterns": {"header": [r"incap_ses", r"x-iinfo"]}},
    "sucuri": {"category": "WAF", "patterns": {"header": [r"x-sucuri-id"]}},
    "mod_security": {"category": "WAF", "patterns": {"header": [r"mod_security"]}},

    # Languages
    "php": {"category": "Programming Language", "patterns": {
        "header": [r"x-powered-by.*php"],
        "cookie": [r"phpsessid"],
        "html": [r"\.php"],
    }},
    "python": {"category": "Programming Language", "patterns": {
        "header": [r"python", r"wsgi", r"uvicorn", r"gunicorn"],
    }},
    "node.js": {"category": "Programming Language", "patterns": {
        "header": [r"x-powered-by.*express", r"express"],
    }},
    "ruby": {"category": "Programming Language", "patterns": {
        "header": [r"x-powered-by.*phusion passenger", r"ruby"],
    }},
    "java": {"category": "Programming Language", "patterns": {
        "header": [r"java", r"tomcat", r"jboss", r"wildfly"],
    }},
    "dotnet": {"category": "Programming Language", "patterns": {
        "header": [r"x-powered-by.*asp\.net", r"x-aspnet-version"],
        "html": [r"\.aspx", r"__viewstate"],
    }},

    # Frameworks
    "django": {"category": "Web Framework", "patterns": {
        "header": [r"csrfmiddlewaretoken"],
        "cookie": [r"csrftoken", r"django"],
        "html": [r"csrfmiddlewaretoken", r"django"],
    }},
    "flask": {"category": "Web Framework", "patterns": {
        "header": [r"server.*werkzeug"],
        "cookie": [r"session=ey"],
    }},
    "fastapi": {"category": "Web Framework", "patterns": {
        "html": [r"fastapi", r"swagger"],
        "path": ["/docs", "/openapi.json"],
    }},
    "express": {"category": "Web Framework", "patterns": {
        "header": [r"x-powered-by.*express"],
    }},
    "laravel": {"category": "Web Framework", "patterns": {
        "cookie": [r"laravel_session"],
        "html": [r"laravel"],
    }},
    "spring": {"category": "Web Framework", "patterns": {
        "header": [r"x-application-context"],
        "cookie": [r"jsessionid"],
    }},
    "rails": {"category": "Web Framework", "patterns": {
        "cookie": [r"_session_id"],
        "header": [r"x-powered-by.*phusion"],
    }},
    "next.js": {"category": "Web Framework", "patterns": {
        "header": [r"x-nextjs"],
        "html": [r"__next", r"_next/static"],
    }},
    "nuxt.js": {"category": "Web Framework", "patterns": {
        "html": [r"__nuxt", r"_nuxt/"],
    }},
    "gatsby": {"category": "Web Framework", "patterns": {
        "html": [r"gatsby", r"___gatsby"],
    }},

    # CMS
    "wordpress": {"category": "CMS", "patterns": {
        "html": [r"wp-content", r"wp-includes", r"wordpress"],
        "cookie": [r"wordpress_"],
        "meta": [r"generator.*wordpress"],
    }},
    "drupal": {"category": "CMS", "patterns": {
        "html": [r"drupal", r"sites/default/files"],
        "header": [r"x-drupal-cache"],
        "meta": [r"generator.*drupal"],
    }},
    "joomla": {"category": "CMS", "patterns": {
        "html": [r"joomla", r"/media/jui/"],
        "meta": [r"generator.*joomla"],
    }},
    "shopify": {"category": "CMS", "patterns": {
        "html": [r"shopify", r"cdn\.shopify\.com"],
        "header": [r"x-shopify"],
    }},
    "squarespace": {"category": "CMS", "patterns": {
        "html": [r"squarespace", r"static\.squarespace"],
    }},
    "wix": {"category": "CMS", "patterns": {
        "html": [r"wix", r"static\.wixstatic"],
    }},
    "webflow": {"category": "CMS", "patterns": {
        "html": [r"webflow", r"assets\.webflow"],
    }},
    "magento": {"category": "CMS", "patterns": {
        "html": [r"magento", r"Mage\.Cookies"],
        "cookie": [r"frontend"],
    }},
    "ghost": {"category": "CMS", "patterns": {
        "html": [r"ghost", r"ghost-/content"],
        "meta": [r"generator.*ghost"],
    }},

    # JavaScript Frameworks
    "react": {"category": "JavaScript Framework", "patterns": {
        "html": [r"react", r"__react", r"_reactroot"],
    }},
    "vue.js": {"category": "JavaScript Framework", "patterns": {
        "html": [r"vue\.js", r"__vue__", r"v-cloak"],
    }},
    "angular": {"category": "JavaScript Framework", "patterns": {
        "html": [r"ng-version", r"angular", r"ng-app"],
    }},
    "svelte": {"category": "JavaScript Framework", "patterns": {
        "html": [r"svelte", r"__svelte"],
    }},
    "jquery": {"category": "JavaScript Library", "patterns": {
        "html": [r"jquery", r"jquery\.min\.js"],
    }},
    "bootstrap": {"category": "CSS Framework", "patterns": {
        "html": [r"bootstrap\.min\.css", r"bootstrap\.min\.js"],
    }},
    "tailwind": {"category": "CSS Framework", "patterns": {
        "html": [r"tailwindcss", r"tailwind"],
    }},

    # Analytics
    "google_analytics": {"category": "Analytics", "patterns": {
        "html": [r"google-analytics\.com/analytics", r"gtag", r"googletagmanager"],
    }},
    "google_tag_manager": {"category": "Analytics", "patterns": {
        "html": [r"googletagmanager\.com/gtm"],
    }},
    "hotjar": {"category": "Analytics", "patterns": {
        "html": [r"hotjar\.com", r"_hjSettings"],
    }},
    "segment": {"category": "Analytics", "patterns": {
        "html": [r"segment\.com/analytics", r"analytics\.load"],
    }},
    "mixpanel": {"category": "Analytics", "patterns": {
        "html": [r"mixpanel\.com", r"mixpanel\.track"],
    }},
    "amplitude": {"category": "Analytics", "patterns": {
        "html": [r"amplitude\.com", r"amplitude\.getInstance"],
    }},

    # Databases (detected via exposed ports/services)
    "mysql": {"category": "Database", "patterns": {"header": [r"mysql"]}},
    "postgresql": {"category": "Database", "patterns": {"header": [r"postgresql"]}},
    "redis": {"category": "Database", "patterns": {"header": [r"redis"]}},
    "mongodb": {"category": "Database", "patterns": {"header": [r"mongodb"]}},
    "elasticsearch": {"category": "Database", "patterns": {"header": [r"elasticsearch"]}},

    # Cloud Providers
    "aws": {"category": "Cloud Provider", "patterns": {
        "header": [r"x-amz-", r"aws"],
        "html": [r"amazonaws\.com"],
    }},
    "gcp": {"category": "Cloud Provider", "patterns": {
        "header": [r"google"],
        "html": [r"googleapis\.com", r"googlecloud"],
    }},
    "azure": {"category": "Cloud Provider", "patterns": {
        "header": [r"x-ms-", r"azure"],
        "html": [r"azure\.com", r"azurewebsites"],
    }},

    # DevOps
    "gitlab": {"category": "DevOps", "patterns": {
        "html": [r"gitlab", r"goname"],
        "header": [r"x-gitlab"],
    }},
    "github_pages": {"category": "DevOps", "patterns": {
        "html": [r"github\.io", r"github pages"],
    }},
    "jenkins": {"category": "DevOps", "patterns": {
        "html": [r"jenkins", r"hudson"],
        "header": [r"x-jenkins"],
    }},
    "grafana": {"category": "DevOps", "patterns": {
        "html": [r"grafana", r"grafana-app"],
    }},
    "kibana": {"category": "DevOps", "patterns": {
        "html": [r"kibana", r"kibana-app"],
    }},

    # Security
    "recaptcha": {"category": "Security", "patterns": {
        "html": [r"recaptcha", r"grecaptcha"],
    }},
    "hcaptcha": {"category": "Security", "patterns": {
        "html": [r"hcaptcha"],
    }},
}


@register_scanner(
    name="technology-intelligence",
    category=ScannerCategory.TECHNOLOGY_FINGERPRINT,
    version="2.0.0",
    priority=ScannerPriority.NORMAL,
    description="Advanced technology fingerprinting with 80+ detection patterns",
    capabilities=[
        "web_server_detection", "cms_detection", "framework_detection",
        "javascript_detection", "cdn_detection", "waf_detection",
        "cloud_detection", "analytics_detection",
    ],
)
class TechnologyIntelligenceScanner(EnhancedBaseScanner):
    """Technology fingerprinting with expanded detection patterns."""

    name = "technology-intelligence"
    version = "2.0.0"
    category = ScannerCategory.TECHNOLOGY_FINGERPRINT
    priority = ScannerPriority.NORMAL

    async def scan(self, target: str, **kwargs) -> ScanResult:

        detected = []
        errors = []

        # Build URLs to check
        urls = [
            f"https://{target}/",
            f"http://{target}/",
            f"https://www.{target}/",
        ]

        for url in urls:
            try:
                async with httpx.AsyncClient(
                    timeout=10, follow_redirects=True, verify=False
                ) as client:
                    resp = await client.get(url)
                    headers = dict(resp.headers)
                    cookies = dict(resp.cookies)
                    body = resp.text[:50000]  # Cap body size

                    # Run fingerprint detection
                    techs = self._detect_technologies(headers, cookies, body, url)
                    detected.extend(techs)

                    if detected:
                        break  # Got results from one URL

            except Exception as e:
                errors.append(f"{url}: {e}")

        # Deduplicate
        seen = set()
        unique = []
        for t in detected:
            key = (t["name"], t["category"])
            if key not in seen:
                seen.add(key)
                unique.append(t)

        return ScanResult(
            success=True,
            scanner=self.name,
            target=target,
            data={
                "hosts": {target: unique},
                "technologies": unique,
                "by_category": self._group_by_category(unique),
                "summary": {
                    "total_detected": len(unique),
                    "categories": list(set(t["category"] for t in unique)),
                },
            },
            errors=errors,
        )

    def validate_target(self, target: str) -> bool:
        return bool(target and "." in target)

    def _detect_technologies(
        self,
        headers: Dict[str, str],
        cookies: Dict[str, str],
        body: str,
        url: str,
    ) -> List[Dict[str, Any]]:
        detected = []
        header_text = " ".join(f"{k}: {v}" for k, v in headers.items()).lower()
        cookie_text = " ".join(f"{k}={v}" for k, v in cookies.items()).lower()
        body_lower = body.lower()

        for name, fp in FINGERPRINTS.items():
            patterns = fp.get("patterns", {})
            confidence = 0

            # Check header patterns
            for pattern in patterns.get("header", []):
                if re.search(pattern, header_text, re.IGNORECASE):
                    confidence = max(confidence, 90)
                    break

            # Check cookie patterns
            for pattern in patterns.get("cookie", []):
                if re.search(pattern, cookie_text, re.IGNORECASE):
                    confidence = max(confidence, 85)
                    break

            # Check HTML patterns
            for pattern in patterns.get("html", []):
                if re.search(pattern, body_lower):
                    confidence = max(confidence, 75)
                    break

            if confidence > 0:
                detected.append({
                    "name": name,
                    "category": fp["category"],
                    "confidence": confidence,
                    "detected_from": url,
                })

        return detected

    def _group_by_category(self, technologies: List[Dict]) -> Dict[str, List[Dict]]:
        grouped: Dict[str, List[Dict]] = {}
        for tech in technologies:
            cat = tech["category"]
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(tech)
        return grouped
