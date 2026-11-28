"""What the web-exposure scanner looks for, and how it proves each hit.

Every rule pairs a path with a *content check*. A path only becomes a
finding when the response body really is the thing named: an ``.env``
must contain ``KEY=value`` lines, a ``.git/HEAD`` must hold a ref, a SQL
dump must contain SQL, an archive must start with archive magic bytes.
That is what keeps sites that answer 200 to every URL ("soft 404") from
flooding customers with false positives.

All checks are single GET requests that any visitor could make. Bodies are
read only up to a small limit (see ``MAX_BODY_BYTES``), so a large exposed
backup is detected from its first bytes and never downloaded.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

MAX_BODY_BYTES = 64 * 1024


@dataclass(frozen=True)
class Probe:
    """Response as seen by a validator."""
    status: int
    headers: Dict[str, str]          # lower-cased names
    body: bytes
    text: str


Validator = Callable[[Probe], bool]


@dataclass(frozen=True)
class ExposureRule:
    rule_id: str
    paths: Tuple[str, ...]
    title: str
    severity: str
    category: str
    check: Validator
    remediation: str = ""
    statuses: Tuple[int, ...] = (200, 206)
    scan_for_secrets: bool = False
    tags: Tuple[str, ...] = field(default_factory=tuple)


def _ct(p: Probe) -> str:
    return p.headers.get("content-type", "").lower()


def _is_html(p: Probe) -> bool:
    head = p.text[:512].lstrip().lower()
    return "text/html" in _ct(p) or head.startswith("<!doctype html") or head.startswith("<html")


def _rx(pattern: str, flags: int = re.I | re.M) -> Validator:
    compiled = re.compile(pattern, flags)
    return lambda p: bool(compiled.search(p.text))


def _not_html_rx(pattern: str, flags: int = re.I | re.M) -> Validator:
    compiled = re.compile(pattern, flags)
    return lambda p: not _is_html(p) and bool(compiled.search(p.text))


def _magic(*prefixes: bytes) -> Validator:
    return lambda p: any(p.body.startswith(m) for m in prefixes)


def _env_file(p: Probe) -> bool:
    if _is_html(p):
        return False
    lines = re.findall(r"^\s*(?:export\s+)?[A-Z][A-Z0-9_]{1,60}\s*=", p.text, re.M)
    return len(lines) >= 2


_ARCHIVE_MAGIC = _magic(
    b"PK\x03\x04",            # zip
    b"\x1f\x8b",              # gzip / tar.gz
    b"7z\xbc\xaf\x27\x1c",    # 7z
    b"Rar!\x1a\x07",          # rar
    b"BZh",                   # bzip2
)
_SQL_DUMP = _not_html_rx(r"(?:^-- (?:MySQL|MariaDB) dump|^-- PostgreSQL database dump|^CREATE TABLE\b|^INSERT INTO\b)")
_DIR_LISTING = _rx(r"<title>\s*(?:Index of /|Directory listing for /)|<h1>\s*Index of /")
_LOGIN_FORM = _rx(r"<input[^>]+type=[\"']?password")


# Paths whose name depends on the host (e.g. example.com.zip) are added by
# ``host_specific_rules``.
RULES: List[ExposureRule] = [
    # ── Secrets and configuration ────────────────────────────────────────
    ExposureRule(
        "exposure/env-file",
        ("/.env", "/.env.local", "/.env.production", "/.env.prod", "/.env.dev",
         "/.env.backup", "/.env.bak", "/.env.old", "/api/.env", "/app/.env"),
        "Environment file (.env) publicly readable", "critical", "secrets_config", _env_file,
        "Remove the file from the web root, block dotfiles at the web server, and rotate every credential it contains.",
        scan_for_secrets=True,
    ),
    ExposureRule(
        "exposure/git-repository", ("/.git/HEAD",),
        "Git repository metadata exposed (.git)", "critical", "source_control",
        _not_html_rx(r"^(?:ref: refs/|[0-9a-f]{40}\s*$)"),
        "Block access to /.git at the web server. Attackers can rebuild the source code and its history, including secrets ever committed.",
    ),
    ExposureRule(
        "exposure/git-config", ("/.git/config",),
        "Git configuration exposed (.git/config)", "high", "source_control",
        _not_html_rx(r"^\[core\]"),
        "Block access to /.git at the web server and check the remote URL for embedded credentials.",
        scan_for_secrets=True,
    ),
    ExposureRule(
        "exposure/svn-repository", ("/.svn/wc.db", "/.svn/entries"),
        "Subversion metadata exposed (.svn)", "high", "source_control",
        lambda p: p.body.startswith(b"SQLite format 3") or (not _is_html(p) and bool(re.match(r"^\d+\s*$", p.text[:5]))),
        "Block access to /.svn at the web server.",
    ),
    ExposureRule(
        "exposure/hg-repository", ("/.hg/hgrc",),
        "Mercurial repository exposed (.hg)", "high", "source_control",
        _not_html_rx(r"^\[(?:paths|ui|extensions)\]"),
        "Block access to /.hg at the web server.",
    ),
    ExposureRule(
        "exposure/ds-store", ("/.DS_Store",),
        "macOS .DS_Store file lists directory contents", "low", "information_disclosure",
        _magic(b"\x00\x00\x00\x01Bud1"),
        "Delete .DS_Store files from the web root; they reveal file and folder names.",
    ),
    ExposureRule(
        "exposure/wordpress-config-backup",
        ("/wp-config.php.bak", "/wp-config.php~", "/wp-config.php.save", "/wp-config.old",
         "/wp-config.php.orig", "/wp-config.txt"),
        "WordPress configuration backup with database credentials", "critical", "secrets_config",
        _rx(r"DB_PASSWORD|AUTH_KEY"),
        "Delete the backup copy and rotate the database password and WordPress salts.",
        scan_for_secrets=True,
    ),
    ExposureRule(
        "exposure/php-config-backup",
        ("/config.php.bak", "/configuration.php.bak", "/config.inc.php.bak", "/settings.php.bak",
         "/configuration.php~", "/config.php~"),
        "PHP configuration backup readable as source", "critical", "secrets_config",
        _rx(r"<\?php[\s\S]{0,4000}(?:password|passwd|secret|db_?pass)"),
        "Delete the backup copy and rotate the credentials it contains.",
        scan_for_secrets=True,
    ),
    ExposureRule(
        "exposure/dotnet-config", ("/web.config", "/appsettings.json", "/appsettings.Production.json"),
        "Application configuration file readable", "high", "secrets_config",
        lambda p: bool(re.search(r"<configuration[\s>]|\"ConnectionStrings\"|\"Logging\"\s*:", p.text)) and not _is_html(p),
        "Stop serving configuration files and rotate any connection strings or keys inside.",
        scan_for_secrets=True,
    ),
    ExposureRule(
        "exposure/spring-config", ("/application.properties", "/application.yml", "/application.yaml"),
        "Spring application configuration readable", "high", "secrets_config",
        _not_html_rx(r"^\s*(?:spring\.|server\.port|spring:)"),
        "Stop serving configuration files and rotate any credentials inside.",
        scan_for_secrets=True,
    ),
    ExposureRule(
        "exposure/docker-compose", ("/docker-compose.yml", "/docker-compose.yaml", "/docker-compose.prod.yml"),
        "docker-compose file readable", "medium", "secrets_config",
        _not_html_rx(r"^services:\s*$|^version:\s*['\"]?\d"),
        "Remove deployment files from the web root; they reveal internal services and often secrets.",
        scan_for_secrets=True,
    ),
    ExposureRule(
        "exposure/npmrc", ("/.npmrc",),
        "npm configuration with registry token", "high", "secrets_config",
        _not_html_rx(r"_authToken|_auth\s*="),
        "Remove .npmrc from the web root and revoke the registry token.",
        scan_for_secrets=True,
    ),
    ExposureRule(
        "exposure/aws-credentials", ("/.aws/credentials", "/.aws/config"),
        "AWS credentials file readable", "critical", "secrets_config",
        _not_html_rx(r"aws_access_key_id|aws_secret_access_key|^\[default\]"),
        "Remove the file and deactivate the access keys in IAM immediately.",
        scan_for_secrets=True,
    ),
    ExposureRule(
        "exposure/ssh-private-key", ("/.ssh/id_rsa", "/.ssh/id_ed25519", "/id_rsa"),
        "SSH private key readable", "critical", "secrets_config",
        _rx(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
        "Remove the key from the web root and replace it everywhere it is authorised.",
    ),
    ExposureRule(
        "exposure/htpasswd", ("/.htpasswd",),
        "Password hash file (.htpasswd) readable", "high", "secrets_config",
        _not_html_rx(r"^[\w.@-]+:(?:\$apr1\$|\$2[aby]\$|\{SHA\}|[./0-9A-Za-z]{13}$)"),
        "Move .htpasswd outside the web root and change the passwords it protects.",
    ),

    # ── Backups and data dumps ───────────────────────────────────────────
    ExposureRule(
        "exposure/sql-dump",
        ("/backup.sql", "/db.sql", "/database.sql", "/dump.sql", "/data.sql", "/mysql.sql",
         "/db_backup.sql", "/site.sql"),
        "Database dump publicly downloadable", "critical", "backup_file", _SQL_DUMP,
        "Delete the dump from the web server, treat its data as leaked, and rotate credentials stored in it.",
        scan_for_secrets=True,
    ),
    ExposureRule(
        "exposure/backup-archive",
        ("/backup.zip", "/backup.tar.gz", "/backup.tgz", "/backup.rar", "/backup.7z",
         "/site.zip", "/site.tar.gz", "/www.zip", "/www.tar.gz", "/public_html.zip",
         "/html.zip", "/web.zip", "/source.zip", "/src.zip", "/archive.zip"),
        "Backup archive publicly downloadable", "high", "backup_file", _ARCHIVE_MAGIC,
        "Delete the archive from the web root; it usually contains source code and configuration.",
    ),

    # ── Debug and diagnostics ────────────────────────────────────────────
    ExposureRule(
        "exposure/phpinfo", ("/phpinfo.php", "/info.php", "/php_info.php", "/test.php"),
        "phpinfo() page exposed", "medium", "debug_endpoint",
        _rx(r"<title>phpinfo\(\)</title>|PHP Version \d"),
        "Delete the page; it reveals paths, modules and sometimes environment secrets.",
        scan_for_secrets=True,
    ),
    ExposureRule(
        "exposure/apache-server-status", ("/server-status",),
        "Apache server-status page exposed", "medium", "debug_endpoint",
        _rx(r"Apache Server Status for"),
        "Restrict /server-status to localhost; it shows live client IPs and requested URLs.",
    ),
    ExposureRule(
        "exposure/spring-actuator-env", ("/actuator/env", "/env", "/manage/env"),
        "Spring Boot actuator /env exposed", "critical", "debug_endpoint",
        _not_html_rx(r"\"(?:propertySources|activeProfiles)\""),
        "Disable or authenticate actuator endpoints (management.endpoints.web.exposure.include).",
        scan_for_secrets=True,
    ),
    ExposureRule(
        "exposure/spring-actuator", ("/actuator",),
        "Spring Boot actuator index exposed", "low", "debug_endpoint",
        _not_html_rx(r"\"_links\"\s*:\s*\{[\s\S]*\"self\""),
        "Expose only the health endpoint publicly.",
    ),
    ExposureRule(
        "exposure/go-pprof", ("/debug/pprof/",),
        "Go pprof profiler exposed", "high", "debug_endpoint",
        _rx(r"Types of profiles available"),
        "Do not register net/http/pprof on a public listener.",
    ),
    ExposureRule(
        "exposure/go-expvar", ("/debug/vars",),
        "Go expvar diagnostics exposed", "medium", "debug_endpoint",
        _not_html_rx(r"\"cmdline\"\s*:\s*\[|\"memstats\"\s*:"),
        "Do not expose expvar publicly; it shows the command line and memory stats.",
    ),
    ExposureRule(
        "exposure/symfony-profiler", ("/_profiler/", "/app_dev.php/_profiler/"),
        "Symfony profiler exposed", "high", "debug_endpoint",
        _rx(r"Symfony Profiler"),
        "Disable debug mode in production.",
    ),
    ExposureRule(
        "exposure/aspnet-trace", ("/trace.axd", "/elmah.axd"),
        "ASP.NET trace / error log exposed", "high", "debug_endpoint",
        _rx(r"Application Trace|Error Log for"),
        "Disable trace.axd and restrict ELMAH to authenticated administrators.",
    ),
    ExposureRule(
        "exposure/werkzeug-debugger", ("/console",),
        "Werkzeug interactive debugger console exposed", "critical", "debug_endpoint",
        _rx(r"Werkzeug(?: powered traceback| Debugger)|Interactive Console"),
        "Never run Flask/Werkzeug with debug=True on a public host; the console allows code execution.",
    ),
    ExposureRule(
        "exposure/laravel-log", ("/storage/logs/laravel.log",),
        "Laravel application log readable", "high", "log_file",
        _not_html_rx(r"^\[\d{4}-\d{2}-\d{2}[ T][\d:]+\] \w+\.(?:ERROR|WARNING|INFO|DEBUG)"),
        "Point the web root at /public only and delete the exposed log.",
        scan_for_secrets=True,
    ),
    ExposureRule(
        "exposure/error-log", ("/error.log", "/error_log", "/debug.log", "/wp-content/debug.log", "/logs/error.log"),
        "Application error log readable", "medium", "log_file",
        _not_html_rx(r"PHP (?:Warning|Notice|Fatal error|Parse error)|\[error\]|Traceback \(most recent call last\)|Exception in thread"),
        "Move logs outside the web root.",
        scan_for_secrets=True,
    ),
    ExposureRule(
        "exposure/prometheus-metrics", ("/metrics",),
        "Prometheus metrics endpoint exposed", "low", "debug_endpoint",
        _not_html_rx(r"^# (?:HELP|TYPE) \w+"),
        "Serve metrics on an internal port or behind authentication.",
    ),

    # ── API surface ──────────────────────────────────────────────────────
    ExposureRule(
        "exposure/openapi-spec",
        ("/swagger.json", "/openapi.json", "/v2/api-docs", "/v3/api-docs", "/api-docs",
         "/api/swagger.json", "/api/openapi.json", "/swagger/v1/swagger.json"),
        "API specification (OpenAPI/Swagger) public", "low", "api_exposure",
        _not_html_rx(r"\"(?:swagger|openapi)\"\s*:\s*\"\d"),
        "Confirm the API is meant to be public; otherwise remove the spec, which maps every endpoint.",
    ),
    ExposureRule(
        "exposure/swagger-ui", ("/swagger-ui.html", "/swagger-ui/", "/swagger/", "/api/docs"),
        "Swagger UI reachable", "low", "api_exposure",
        _rx(r"<title>\s*Swagger UI|swagger-ui-bundle"),
        "Restrict interactive API docs to internal users if the API is not public.",
    ),
    ExposureRule(
        "exposure/graphql-endpoint", ("/graphql", "/api/graphql"),
        "GraphQL endpoint reachable", "info", "api_exposure",
        lambda p: bool(re.search(r"must provide (?:a )?query|GraphQL|\"errors\"\s*:\s*\[", p.text)) and "graphql" in (p.text.lower() + _ct(p)),
        "Check that introspection is disabled in production and every resolver enforces authorisation.",
        statuses=(200, 400, 405),
    ),

    # ── Directory listings ───────────────────────────────────────────────
    ExposureRule(
        "exposure/directory-listing",
        ("/uploads/", "/upload/", "/files/", "/backup/", "/backups/", "/wp-content/uploads/",
         "/images/", "/assets/", "/static/", "/tmp/", "/logs/", "/data/", "/export/"),
        "Open directory listing", "medium", "directory_listing", _DIR_LISTING,
        "Disable auto-indexing (Options -Indexes / autoindex off) and check what files were listed.",
    ),

    # ── Admin and management panels (detected, never logged in to) ─────
    ExposureRule(
        "panel/phpmyadmin", ("/phpmyadmin/", "/phpMyAdmin/", "/pma/", "/dbadmin/"),
        "phpMyAdmin reachable from the internet", "high", "admin_panel",
        _rx(r"<title>[^<]*phpMyAdmin|pma_password"),
        "Restrict database admin tools to a VPN or allow-listed IPs.",
    ),
    ExposureRule(
        "panel/adminer", ("/adminer.php", "/adminer/"),
        "Adminer database tool reachable", "high", "admin_panel",
        _rx(r"<title>[^<]*Adminer|adminer\.org"),
        "Remove Adminer from production or restrict it to allow-listed IPs.",
    ),
    ExposureRule(
        "panel/tomcat-manager", ("/manager/html",),
        "Tomcat Manager reachable", "high", "admin_panel",
        lambda p: "tomcat" in p.headers.get("www-authenticate", "").lower() or "Tomcat Web Application Manager" in p.text,
        "Bind the manager app to localhost or remove it.",
        statuses=(200, 401),
    ),
    ExposureRule(
        "panel/jenkins", ("/jenkins/", "/login"),
        "Jenkins reachable from the internet", "high", "admin_panel",
        lambda p: "x-jenkins" in p.headers or bool(re.search(r"<title>[^<]*Jenkins", p.text)),
        "Put Jenkins behind SSO/VPN; exposed instances are a common breach path.",
        statuses=(200, 403),
    ),
    ExposureRule(
        "panel/grafana", ("/grafana/login", "/login"),
        "Grafana login reachable", "medium", "admin_panel",
        _rx(r"<title>Grafana</title>|grafana-app"),
        "Restrict Grafana to internal users or enforce SSO.",
    ),
    ExposureRule(
        "panel/kibana", ("/app/kibana", "/app/home"),
        "Kibana reachable", "high", "admin_panel",
        lambda p: "kbn-name" in p.headers or "kbn-license-sig" in p.headers or bool(re.search(r"<title>(?:Elastic|Kibana)", p.text)),
        "Put Kibana behind authentication; it exposes indexed data.",
    ),
    ExposureRule(
        "panel/solr", ("/solr/",),
        "Apache Solr admin reachable", "high", "admin_panel",
        _rx(r"<title>Solr Admin"),
        "Restrict Solr admin to internal networks.",
    ),
    ExposureRule(
        "panel/jupyter", ("/tree", "/lab"),
        "Jupyter notebook server reachable", "high", "admin_panel",
        _rx(r"<title>(?:Home - )?Jupyter|jupyter-config-data"),
        "Require a token/password and do not expose notebook servers publicly; they allow code execution.",
    ),
    ExposureRule(
        "panel/h2-console", ("/h2-console/", "/h2/"),
        "H2 database console reachable", "high", "admin_panel",
        _rx(r"H2 Console|h2-console"),
        "Disable the H2 web console in production.",
    ),
    ExposureRule(
        "panel/wordpress-login", ("/wp-login.php",),
        "WordPress login page reachable", "info", "admin_panel",
        _rx(r"wp-submit|user_login"),
        "Consider rate limiting, 2FA and an allow-list for wp-admin.",
    ),
    ExposureRule(
        "panel/generic-admin-login", ("/admin/", "/administrator/", "/admin/login", "/backend/", "/manage/"),
        "Admin login page reachable", "low", "admin_panel", _LOGIN_FORM,
        "Restrict admin interfaces to a VPN or allow-listed IPs and require MFA.",
    ),
]

# Signatures checked against the *root page* of every web service, so a
# panel running at "/" on its own port (Jenkins on :8080, Grafana on :3000,
# Elasticsearch on :9200...) is caught without extra requests.
ROOT_SIGNATURES: List[Tuple[str, str, str, Validator]] = [
    ("panel/jenkins", "Jenkins reachable from the internet", "high",
     lambda p: "x-jenkins" in p.headers or bool(re.search(r"<title>[^<]*Jenkins", p.text))),
    ("panel/grafana", "Grafana login reachable", "medium", _rx(r"<title>Grafana</title>")),
    ("panel/kibana", "Kibana reachable", "high", lambda p: "kbn-name" in p.headers),
    ("service/elasticsearch-open", "Elasticsearch answers without authentication", "critical",
     lambda p: "\"cluster_name\"" in p.text and "You Know, for Search" in p.text),
    ("service/couchdb-open", "CouchDB answers without authentication", "high",
     lambda p: "\"couchdb\"" in p.text and "Welcome" in p.text),
    ("panel/rabbitmq", "RabbitMQ management UI reachable", "medium", _rx(r"<title>RabbitMQ Management")),
    ("panel/portainer", "Portainer reachable", "high", _rx(r"<title>Portainer")),
    ("panel/webmin", "Webmin reachable", "high", _rx(r"<title>[^<]*Webmin|Login to Webmin")),
    ("panel/cpanel", "cPanel/WHM login reachable", "low", _rx(r"<title>(?:cPanel|WHM) Login")),
    ("panel/plesk", "Plesk login reachable", "low", _rx(r"<title>Plesk")),
    ("panel/kubernetes-dashboard", "Kubernetes dashboard reachable", "critical", _rx(r"<title>Kubernetes Dashboard")),
    ("panel/traefik", "Traefik dashboard reachable", "high", _rx(r"<title>Traefik")),
    ("panel/argocd", "Argo CD reachable", "medium", _rx(r"<title>Argo CD")),
    ("panel/sonarqube", "SonarQube reachable", "medium", _rx(r"<title>SonarQube")),
    ("panel/gitlab", "GitLab sign-in reachable", "info", _rx(r"<title>Sign in · GitLab")),
    ("panel/jupyter", "Jupyter notebook server reachable", "high", _rx(r"<title>(?:Home - )?Jupyter")),
    ("panel/phpmyadmin", "phpMyAdmin reachable from the internet", "high", _rx(r"<title>[^<]*phpMyAdmin")),
    ("exposure/directory-listing", "Open directory listing", "medium", _DIR_LISTING),
    ("exposure/werkzeug-debugger", "Werkzeug debugger traceback exposed", "high",
     _rx(r"Werkzeug powered traceback interpreter")),
    ("exposure/stack-trace", "Application stack trace in public response", "medium",
     _rx(r"Traceback \(most recent call last\)|at java\.lang\.|org\.springframework\.|Fatal error</b>:")),
]


def host_specific_paths(host: str) -> List[str]:
    """Backups named after the site, e.g. /example.com.zip, /example.sql."""
    labels = [host]
    first = host.split(".")[0]
    if first and first not in ("www",):
        labels.append(first)
    parts = host.split(".")
    if len(parts) >= 2:
        labels.append(parts[-2])
    out: List[str] = []
    for label in dict.fromkeys(labels):
        for ext in (".zip", ".tar.gz", ".sql", ".sql.gz", ".bak"):
            out.append(f"/{label}{ext}")
    return out


def host_specific_rules(host: str) -> List[ExposureRule]:
    paths = host_specific_paths(host)
    archive = tuple(p for p in paths if p.endswith((".zip", ".tar.gz", ".sql.gz", ".bak")))
    sql = tuple(p for p in paths if p.endswith(".sql"))
    return [
        ExposureRule(
            "exposure/backup-archive", archive, "Backup archive publicly downloadable", "high",
            "backup_file", _ARCHIVE_MAGIC,
            "Delete the archive from the web root; it usually contains source code and configuration.",
        ),
        ExposureRule(
            "exposure/sql-dump", sql, "Database dump publicly downloadable", "critical",
            "backup_file", _SQL_DUMP,
            "Delete the dump from the web server, treat its data as leaked, and rotate credentials stored in it.",
            scan_for_secrets=True,
        ),
    ]


def match_root_signatures(probe: Probe) -> List[Tuple[str, str, str]]:
    hits = []
    for rule_id, title, severity, check in ROOT_SIGNATURES:
        try:
            if check(probe):
                hits.append((rule_id, title, severity))
        except Exception:  # noqa: BLE001 — a bad signature must not end the scan
            continue
    return hits


def find_rule(rule_id: str) -> Optional[ExposureRule]:
    for r in RULES:
        if r.rule_id == rule_id:
            return r
    return None
