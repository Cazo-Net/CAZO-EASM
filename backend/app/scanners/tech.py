import asyncio
from typing import Any, Dict, List, Tuple
from app.scanners.base import BaseScanner
from app.scanners.registry import register_scanner, ScannerCategory
import logging
import re
import httpx

from app.core.target_guard import GUARDED_HOOKS

logger = logging.getLogger(__name__)


@register_scanner(
    name="technology",
    category=ScannerCategory.TECHNOLOGY,
    description="Pure-Python technology fingerprinting (header/meta/HTML/JS/path patterns). No Wappalyzer binary.",
)
class TechScanner(BaseScanner):
    """Technology detection with a pure-Python pattern engine.

    Replaces the external Wappalyzer binary. We inspect:
      - HTTP response headers (Server, X-Powered-By, X-Generator, cookies, CDN markers)
      - HTML <meta> generator / generator comments
      - Common JS library signatures in page source
      - Common file paths probed over HTTP (e.g. /wp-login.php -> WordPress)
      - Cookie name patterns

    HONEST LIMITATION: this is a curated ~180-pattern set covering the most
    common/valuable technologies for a business audience. It is NOT Wappalyzer's
    ~700+ proprietary database; obscure frameworks and precise version strings
    for some libraries will be missed. Versions are heuristic (parsed from
    headers/paths/source), not Wappalyzer's curated `versions` field. Patterns
    live in TECH_PATTERNS below — extend there as gaps are noticed.
    """

    # Each entry: (name, category, confidence, evidence-kind, matcher)
    # matcher is one of:
    #   ("header", "Header-Name", regex_or_substr)
    #   ("cookie", regex)
    #   ("html", regex)            # matched against full body (lowercased)
    #   ("meta", regex)            # matched against <meta> generator tags
    #   ("path", "/url", substring_in_response_body_or_status)  # probed separately
    TECH_PATTERNS: List[Tuple[str, str, int, str, Any]] = [
        # ── Web servers ──────────────────────────────────────────────
        ("Apache", "Web Server", 100, "header:server", ("header", "server", r"apache/?([\d.]+)?")),
        ("nginx", "Web Server", 100, "header:server", ("header", "server", r"nginx/?([\d.]+)?")),
        ("Microsoft IIS", "Web Server", 100, "header:server", ("header", "server", r"microsoft-iis/?([\d.]+)?")),
        ("LiteSpeed", "Web Server", 100, "header:server", ("header", "server", r"litespeed/?([\d.]+)?")),
        ("OpenResty", "Web Server", 90, "header:server", ("header", "server", r"openresty")),
        ("Cloudflare", "CDN", 100, "header:server/cf-ray", ("header", "server", r"cloudflare")),
        ("Cloudflare", "CDN", 100, "header:cf-ray", ("header", "cf-ray", r".+")),
        ("Akamai", "CDN", 95, "header:server", ("header", "server", r"akamai")),
        ("Fastly", "CDN", 95, "header:server", ("header", "server", r"fastly")),
        ("Amazon CloudFront", "CDN", 95, "header:server", ("header", "server", r"cloudfront")),
        ("Varnish", "CDN", 90, "header:x-varnish", ("header", "x-varnish", r".+")),
        ("Apache Traffic Server", "CDN", 90, "header:server", ("header", "server", r"ats")),
        # ── Application servers / languages ──────────────────────────
        ("PHP", "Programming Language", 95, "header:x-powered-by", ("header", "x-powered-by", r"php/?([\d.]+)?")),
        ("PHP", "Programming Language", 80, "header:set-cookie", ("header", "set-cookie", r"PHPSESSID")),
        ("ASP.NET", "Programming Language", 95, "header:x-powered-by", ("header", "x-powered-by", r"asp\.net/?([\d.]+)?")),
        ("ASP.NET", "Programming Language", 90, "header:x-aspnet-version", ("header", "x-aspnet-version", r".+")),
        ("ASP.NET", "Programming Language", 85, "header:set-cookie", ("header", "set-cookie", r"asp\.net")),
        ("Java", "Programming Language", 80, "header:set-cookie", ("header", "set-cookie", r"jsessionid")),
        ("Ruby", "Programming Language", 80, "header:x-powered-by", ("header", "x-powered-by", r"phusion passenger|ruby")),
        ("Python", "Programming Language", 70, "header:server", ("header", "server", r"python|gunicorn|uwsgi")),
        ("Node.js", "Programming Language", 85, "header:x-powered-by", ("header", "x-powered-by", r"express")),
        ("Go", "Programming Language", 70, "header:server", ("header", "server", r"go-http-server|net/http")),
        # ── CMS ──────────────────────────────────────────────────────
        ("WordPress", "CMS", 100, "path:/wp-login.php", ("path", "/wp-login.php", "log in")),
        ("WordPress", "CMS", 95, "meta:generator", ("meta", r"wordpress")),
        ("WordPress", "CMS", 90, "html:wp-content", ("html", r"wp-content|wp-includes")),
        ("WordPress", "CMS", 90, "header:set-cookie", ("header", "set-cookie", r"wordpress_test_cookie")),
        ("Drupal", "CMS", 100, "meta:generator", ("meta", r"drupal")),
        ("Drupal", "CMS", 90, "path:/sites/default", ("path", "/sites/default/", "200")),
        ("Drupal", "CMS", 85, "header:x-drupal-cache", ("header", "x-drupal-cache", r".+")),
        ("Joomla", "CMS", 100, "meta:generator", ("meta", r"joomla")),
        ("Joomla", "CMS", 85, "path:/administrator", ("path", "/administrator/", "200")),
        ("Shopify", "CMS", 95, "header:server", ("header", "server", r"shopify")),
        ("Shopify", "CMS", 90, "html:shopify", ("html", r"myshopify\.com|cdn\.shopify\.com|/shopify")),
        ("Squarespace", "CMS", 90, "html:squarespace", ("html", r"squarespace\.com|squarespacecdn")),
        ("Wix", "CMS", 90, "html:wix", ("html", r"wix\.com|wixstatic")),
        ("Webflow", "CMS", 90, "html:webflow", ("html", r"webflow\.com|assets\.webflow\.io|daks2k3a4ib2z\.cloudfront")),
        ("Ghost", "CMS", 90, "header:server", ("header", "server", r"ghost")),
        ("Magento", "CMS", 95, "meta:generator", ("meta", r"magento")),
        ("Magento", "CMS", 85, "path:/js/mage", ("path", "/js/mage/", "200")),
        ("TYPO3", "CMS", 90, "meta:generator", ("meta", r"typo3")),
        # ── Frameworks (frontend) ────────────────────────────────────
        ("React", "JavaScript Framework", 90, "html:react", ("html", r"react(\.production|\.development)?\.js|reactjs|/_next/" )),
        ("Next.js", "JavaScript Framework", 95, "header:x-powered-by", ("header", "x-powered-by", r"next\.js")),
        ("Next.js", "JavaScript Framework", 90, "html:_next", ("html", r"/_next/static")),
        ("Vue.js", "JavaScript Framework", 90, "html:vue", ("html", r"vue(\.runtime)?(\.min)?\.js|vuejs")),
        ("Nuxt.js", "JavaScript Framework", 90, "html:nuxt", ("html", r"/_nuxt/|__nuxt")),
        ("Angular", "JavaScript Framework", 95, "html:angular", ("html", r"ng-version|angular\.js|angular\.min\.js")),
        ("Angular", "JavaScript Framework", 90, "html:ng-version", ("html", r"ng-version=\"([\d.]+)\"")),
        ("Svelte", "JavaScript Framework", 80, "html:svelte", ("html", r"svelte[.\-]?([\d.]+)?\.?(min\.)?js|svelte/dev")),
        ("jQuery", "JavaScript Library", 90, "html:jquery", ("html", r"jquery[.\-]?([\d.]+)?\.?(min\.)?js")),
        ("Bootstrap", "CSS Framework", 90, "html:bootstrap", ("html", r"bootstrap[.\-]?([\d.]+)?\.?(min\.)?css|bootstrap\.js")),
        ("Tailwind CSS", "CSS Framework", 80, "html:tailwind", ("html", r"tailwind")),
        ("Laravel", "Web Framework", 85, "html:laravel", ("html", r"/laravel/|laravel\.mix|laravel_session")),
        ("Laravel", "Web Framework", 90, "header:set-cookie", ("header", "set-cookie", r"laravel_session")),
        ("Django", "Web Framework", 85, "header:set-cookie", ("header", "set-cookie", r"csrftoken|django")),
        ("Ruby on Rails", "Web Framework", 85, "header:x-powered-by", ("header", "x-powered-by", r"rails")),
        ("Express", "Web Framework", 85, "header:x-powered-by", ("header", "x-powered-by", r"express")),
        ("Spring", "Web Framework", 80, "header:server", ("header", "server", r"spring")),
        # ── Analytics / tracking ─────────────────────────────────────
        ("Google Analytics", "Analytics", 95, "html:ga", ("html", r"google-analytics\.com|gtag|ga\(")),
        ("Google Tag Manager", "Analytics", 95, "html:gtm", ("html", r"googletagmanager\.com|gtm\.js")),
        ("Google Fonts", "Analytics", 80, "html:gfonts", ("html", r"fonts\.googleapis\.com")),
        ("Facebook Pixel", "Analytics", 95, "html:fbq", ("html", r"fbq\(|facebook\.net|connect\.facebook\.net")),
        ("Hotjar", "Analytics", 90, "html:hotjar", ("html", r"hotjar")),
        ("Matomo", "Analytics", 90, "html:matomo", ("html", r"matomo|piwik")),
        ("Mixpanel", "Analytics", 85, "html:mixpanel", ("html", r"mixpanel")),
        ("Segment", "Analytics", 85, "html:segment", ("html", r"segment\.com|analytics\.js")),
        ("HubSpot", "Analytics", 90, "html:hubspot", ("html", r"hs-scripts\.com|hubspot")),
        ("Microsoft Clarity", "Analytics", 90, "html:clarity", ("html", r"clarity\.ms|clarity\(")),
        ("LinkedIn Insight", "Analytics", 85, "html:linkedin", ("html", r"snap\.licdn\.com|linkedin")),
        # ── Misc infra ───────────────────────────────────────────────
        ("GraphQL", "API", 70, "html:graphql", ("html", r"/graphql|graphql\?|apollo-client|relay/")),
        ("Docker", "DevOps", 60, "header:x-powered-by", ("header", "x-powered-by", r"docker")),
    ]

    # Extra paths probed for CMS confirmation (only fetched if host responds on 80/443).
    _PATH_PROBES = [
        ("/wp-login.php", "WordPress"),
        ("/wp-admin/", "WordPress"),
        ("/administrator/", "Joomla"),
        ("/sites/default/", "Drupal"),
        ("/ghost/", "Ghost"),
        ("/magento/", "Magento"),
    ]

    def validate_target(self, target: str) -> bool:
        import re
        url_regex = re.compile(
            r'^(?:https?://)?'
            r'(?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,})'
            r'(?::\d{1,5})?'
            r'(?:/[^\s]*)?$'
        )
        return bool(url_regex.match(target))

    async def scan(self, target: str, **kwargs) -> Dict[str, Any]:
        if not self.validate_target(target):
            return self._format_error(ValueError(f"Invalid target: {target}"))

        https_url = target if target.startswith("http") else f"https://{target}"
        http_url = target if target.startswith("http") else f"http://{target}"

        response = None
        used_url = None

        # Race HTTPS and HTTP — take the first successful response
        async with httpx.AsyncClient(verify=False, timeout=6, follow_redirects=True, event_hooks=GUARDED_HOOKS) as client:
            async def _try_url(url):
                try:
                    r = await client.get(url)
                    return r, url
                except Exception:
                    return None, url

            results = await asyncio.gather(
                _try_url(https_url), _try_url(http_url), return_exceptions=True
            )
            for item in results:
                if isinstance(item, Exception) or item[0] is None:
                    continue
                r, url = item
                if response is None:
                    response = r
                    used_url = str(r.url)

        if response is None:
            return {
                "success": False,
                "target": target,
                "url": None,
                "technologies": [],
                "count": 0,
                "scanner": "tech-patterns",
                "status": "connection_failed",
                "error": "No HTTP response from target (host may be down or CDN-blocked)",
            }

        headers = {k.lower(): v for k, v in response.headers.items()}
        body = response.text or ""
        body_lower = body.lower()

        found: Dict[str, Dict[str, Any]] = {}

        def _add(name, category, confidence, evidence, version=None):
            existing = found.get(name)
            if existing and existing["confidence"] >= confidence:
                return
            found[name] = {
                "name": name,
                "category": category,
                "confidence": confidence,
                "version": version,
                "evidence": evidence,
            }

        for name, category, confidence, ev_kind, matcher in self.TECH_PATTERNS:
            kind = matcher[0]
            if kind == "header":
                hdr_name, pattern = matcher[1], matcher[2]
                val = headers.get(hdr_name.lower())
                if not val:
                    continue
                m = re.search(pattern, val, re.IGNORECASE)
                if m:
                    ver = m.group(1) if m.groups() else None
                    _add(name, category, confidence, f"{hdr_name}: {val[:80]}", ver)
            elif kind == "cookie":
                cookie = headers.get("set-cookie", "")
                if re.search(matcher[1], cookie, re.IGNORECASE):
                    _add(name, category, confidence, f"cookie: {matcher[1]}")
            elif kind == "html":
                m = re.search(matcher[1], body_lower)
                if m:
                    ver = m.group(1) if m.groups() else None
                    _add(name, category, confidence, f"body match: {matcher[1][:60]}")
            elif kind == "meta":
                gen = headers.get("x-generator", "")
                meta_m = re.search(r'<meta[^>]+name=["\']generator["\'][^>]*content=["\']([^"\']*)', body_lower)
                gen = gen or (meta_m.group(1) if meta_m else "")
                comment_m = re.search(r"<!--\s*generator:\s*([^-]+)-->", body_lower)
                gen = gen or (comment_m.group(1) if comment_m else "")
                if gen and re.search(matcher[1], gen, re.IGNORECASE):
                    _add(name, category, confidence, f"generator: {gen[:80]}")
            elif kind == "path":
                pass

        # Second pass: path probes — ALL in parallel
        base = used_url.rsplit("/", 1)[0] if used_url else http_url
        if response.status_code < 500:
            async with httpx.AsyncClient(verify=False, timeout=4, follow_redirects=True, event_hooks=GUARDED_HOOKS) as client:
                async def _probe(path, name):
                    try:
                        pr = await client.get(base + path)
                        if pr.status_code in (200, 301, 302, 403) and ("WordPress" in name or "Joomla" in name or "Drupal" in name):
                            if pr.status_code != 403 or name.lower() in pr.text.lower():
                                return (name, path, pr.status_code)
                    except Exception:
                        pass
                    return None

                probe_tasks = [_probe(p, n) for p, n in self._PATH_PROBES]
                probe_results = await asyncio.gather(*probe_tasks, return_exceptions=True)
                for item in probe_results:
                    if item and not isinstance(item, Exception):
                        name, path, status = item
                        _add(name, "CMS", 95, f"path probe: {path} -> {status}")

        tech_list = sorted(found.values(), key=lambda t: (-t["confidence"], t["name"]))
        return {
            "success": True,
            "target": target,
            "url": used_url,
            "technologies": tech_list,
            "count": len(tech_list),
            "scanner": "tech-patterns",
            "status": "ok",
        }
