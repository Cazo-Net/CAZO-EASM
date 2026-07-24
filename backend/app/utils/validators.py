import re


def validate_domain(domain: str) -> bool:
    """Validate domain name format."""
    domain_regex = re.compile(
        r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    )
    return bool(domain_regex.match(domain))


def validate_ip(ip: str) -> bool:
    """Validate IPv4 address format."""
    ip_regex = re.compile(
        r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
        r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    )
    return bool(ip_regex.match(ip))


def validate_email(email: str) -> bool:
    """Validate email format."""
    email_regex = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    return bool(email_regex.match(email))


def sanitize_input(value: str, max_length: int = 255) -> str:
    """Sanitize general string input — strips HTML tags and control characters."""
    value = value.strip()
    value = re.sub(r'<[^>]+>', '', value)
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)
    return value[:max_length]


def sanitize_slug(slug: str) -> str:
    """Sanitize slug — lowercase alphanumeric and hyphens only."""
    slug = slug.lower().strip()
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    return slug[:100]


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file system use."""
    sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
    return sanitized[:255]


def truncate_string(s: str, max_length: int = 100) -> str:
    """Truncate string with ellipsis if too long."""
    if len(s) <= max_length:
        return s
    return s[:max_length-3] + "..."
