"""Shared ASN resolution utility.

Both the relationships scanner and the asset-backfill layer need to map an IP
address to its owning Autonomous System (ASN) + provider. The mapping is a
best-effort, in-code prefix table covering the major cloud/hosting/CDN
providers; it is intentionally conservative — only well-known provider ranges
are listed so that a match implies co-tenancy on shared infrastructure (used as
a *weak* shadow-asset signal, not proof of ownership).

NOTE: This is a hardcoded approximation, not a live IP-to-ASN database. It will
miss smaller/regional providers and private/enterprise ASNs (which correctly
fall through to "no match" and are treated as dedicated infra). For production
accuracy, swap :func:`resolve_asn` for a query against a published IP-to-ASN
feed (e.g. MaxMind GeoASN, RIPE RIS, or a paid enrichment API). The contract
below (``{"asn", "provider"}`` or ``None``) must be preserved if replaced.
"""
from ipaddress import ip_network, ip_address
from typing import Dict, Optional


# (prefix, asn, provider) — only major, unambiguously-shared infrastructure.
_ASN_ENTRIES = [
    # --- Cloudflare ---
    ("104.16.0.0/12", "AS13335", "Cloudflare"),
    ("172.64.0.0/13", "AS13335", "Cloudflare"),
    ("103.21.244.0/22", "AS13335", "Cloudflare"),
    ("103.22.200.0/23", "AS13335", "Cloudflare"),
    ("103.31.4.0/23", "AS13335", "Cloudflare"),
    ("141.101.64.0/18", "AS13335", "Cloudflare"),
    ("162.158.0.0/15", "AS13335", "Cloudflare"),
    ("198.41.128.0/17", "AS13335", "Cloudflare"),
    # --- Amazon AWS ---
    ("13.32.0.0/12", "AS16509", "Amazon AWS"),
    ("13.35.0.0/16", "AS16509", "Amazon AWS"),
    ("18.64.0.0/14", "AS16509", "Amazon AWS"),
    ("52.0.0.0/8", "AS16509", "Amazon AWS"),
    ("54.0.0.0/8", "AS16509", "Amazon AWS"),
    ("3.0.0.0/8", "AS16509", "Amazon AWS"),
    ("35.0.0.0/8", "AS16509", "Amazon AWS"),
    # --- Google Cloud ---
    ("35.0.0.0/8", "AS15169", "Google Cloud"),
    ("130.211.0.0/16", "AS15169", "Google Cloud"),
    ("34.0.0.0/8", "AS15169", "Google Cloud"),
    ("146.148.0.0/16", "AS15169", "Google Cloud"),
    ("9.0.0.0/8", "AS15169", "Google Cloud"),
    # --- Microsoft Azure ---
    ("40.0.0.0/8", "AS8075", "Microsoft Azure"),
    ("13.64.0.0/11", "AS8075", "Microsoft Azure"),
    ("52.96.0.0/12", "AS8075", "Microsoft Azure"),
    ("104.208.0.0/13", "AS8075", "Microsoft Azure"),
    ("20.0.0.0/8", "AS8075", "Microsoft Azure"),
    ("104.40.0.0/13", "AS8075", "Microsoft Azure"),
    # --- Akamai ---
    ("23.0.0.0/12", "AS20940", "Akamai"),
    ("23.32.0.0/11", "AS20940", "Akamai"),
    ("23.64.0.0/11", "AS20940", "Akamai"),
    ("23.192.0.0/11", "AS20940", "Akamai"),
    ("104.64.0.0/10", "AS20940", "Akamai"),
    ("104.96.0.0/11", "AS20940", "Akamai"),
    ("104.108.0.0/14", "AS20940", "Akamai"),
    ("172.224.0.0/11", "AS20940", "Akamai"),
    ("172.236.0.0/14", "AS20940", "Akamai"),
    ("184.24.0.0/13", "AS20940", "Akamai"),
    ("184.50.0.0/15", "AS20940", "Akamai"),
    ("184.84.0.0/14", "AS20940", "Akamai"),
    ("184.96.0.0/14", "AS20940", "Akamai"),
    ("184.128.0.0/13", "AS20940", "Akamai"),
    ("2.16.0.0/12", "AS20940", "Akamai"),
    ("95.100.0.0/15", "AS20940", "Akamai"),
    ("95.101.0.0/16", "AS20940", "Akamai"),
    # --- Fastly ---
    ("151.101.0.0/16", "AS54113", "Fastly"),
    ("151.137.0.0/16", "AS54113", "Fastly"),
    ("157.52.0.0/16", "AS54113", "Fastly"),
    ("167.82.0.0/16", "AS54113", "Fastly"),
    ("199.232.0.0/16", "AS54113", "Fastly"),
    ("146.75.0.0/16", "AS54113", "Fastly"),
    ("104.156.80.0/20", "AS54113", "Fastly"),
    ("185.31.16.0/22", "AS54113", "Fastly"),
    # --- DigitalOcean ---
    ("142.93.0.0/16", "AS14061", "DigitalOcean"),
    ("143.198.0.0/16", "AS14061", "DigitalOcean"),
    ("146.190.0.0/16", "AS14061", "DigitalOcean"),
    ("159.89.0.0/16", "AS14061", "DigitalOcean"),
    ("167.99.0.0/16", "AS14061", "DigitalOcean"),
    ("178.62.0.0/16", "AS14061", "DigitalOcean"),
    ("188.166.0.0/16", "AS14061", "DigitalOcean"),
    ("192.241.128.0/17", "AS14061", "DigitalOcean"),
    ("206.189.0.0/16", "AS14061", "DigitalOcean"),
    ("64.225.0.0/16", "AS14061", "DigitalOcean"),
    ("68.183.0.0/16", "AS14061", "DigitalOcean"),
    ("137.184.0.0/16", "AS14061", "DigitalOcean"),
    ("161.35.0.0/16", "AS14061", "DigitalOcean"),
    ("164.90.0.0/16", "AS14061", "DigitalOcean"),
    ("209.97.0.0/16", "AS14061", "DigitalOcean"),
    ("157.245.0.0/16", "AS14061", "DigitalOcean"),
    ("174.138.0.0/16", "AS14061", "DigitalOcean"),
    # --- Linode (now Akamai, distinct ranges) ---
    ("23.239.0.0/16", "AS63949", "Linode"),
    ("45.33.0.0/16", "AS63949", "Linode"),
    ("50.116.0.0/16", "AS63949", "Linode"),
    ("66.228.0.0/16", "AS63949", "Linode"),
    ("74.207.0.0/16", "AS63949", "Linode"),
    ("96.126.0.0/16", "AS63949", "Linode"),
    ("97.107.0.0/16", "AS63949", "Linode"),
    ("139.162.0.0/16", "AS63949", "Linode"),
    ("172.104.0.0/16", "AS63949", "Linode"),
    ("173.230.0.0/16", "AS63949", "Linode"),
    ("178.79.0.0/16", "AS63949", "Linode"),
    ("192.155.0.0/16", "AS63949", "Linode"),
    ("198.58.0.0/16", "AS63949", "Linode"),
    ("212.71.0.0/16", "AS63949", "Linode"),
    ("45.79.0.0/16", "AS63949", "Linode"),
    ("176.58.0.0/16", "AS63949", "Linode"),
    ("104.200.0.0/16", "AS63949", "Linode"),
    # --- Vultr ---
    ("45.32.0.0/16", "AS20473", "Vultr"),
    ("108.61.0.0/16", "AS20473", "Vultr"),
    ("104.207.128.0/17", "AS20473", "Vultr"),
    ("107.191.0.0/16", "AS20473", "Vultr"),
    ("144.202.0.0/16", "AS20473", "Vultr"),
    ("149.28.0.0/16", "AS20473", "Vultr"),
    ("155.138.0.0/16", "AS20473", "Vultr"),
    ("156.67.0.0/16", "AS20473", "Vultr"),
    ("207.246.0.0/16", "AS20473", "Vultr"),
    ("208.167.0.0/16", "AS20473", "Vultr"),
    # --- OVH ---
    ("51.38.0.0/16", "AS16276", "OVH"),
    ("51.68.0.0/16", "AS16276", "OVH"),
    ("51.75.0.0/16", "AS16276", "OVH"),
    ("51.77.0.0/16", "AS16276", "OVH"),
    ("51.89.0.0/16", "AS16276", "OVH"),
    ("51.91.0.0/16", "AS16276", "OVH"),
    ("51.158.0.0/16", "AS16276", "OVH"),
    ("54.36.0.0/16", "AS16276", "OVH"),
    ("54.37.0.0/16", "AS16276", "OVH"),
    ("54.38.0.0/16", "AS16276", "OVH"),
    ("145.239.0.0/16", "AS16276", "OVH"),
    ("151.80.0.0/16", "AS16276", "OVH"),
    ("163.172.0.0/16", "AS16276", "OVH"),
    ("188.165.0.0/16", "AS16276", "OVH"),
    ("213.186.0.0/16", "AS16276", "OVH"),
    ("57.128.0.0/16", "AS16276", "OVH"),
    ("15.204.0.0/16", "AS16276", "OVH"),
    ("149.56.0.0/16", "AS16276", "OVH"),
    ("158.69.0.0/16", "AS16276", "OVH"),
    # --- Oracle Cloud ---
    ("129.146.0.0/16", "AS31898", "Oracle Cloud"),
    ("129.147.0.0/16", "AS31898", "Oracle Cloud"),
    ("129.148.0.0/16", "AS31898", "Oracle Cloud"),
    ("129.149.0.0/16", "AS31898", "Oracle Cloud"),
    ("129.150.0.0/16", "AS31898", "Oracle Cloud"),
    ("129.151.0.0/16", "AS31898", "Oracle Cloud"),
    ("129.152.0.0/16", "AS31898", "Oracle Cloud"),
    ("129.153.0.0/16", "AS31898", "Oracle Cloud"),
    ("129.154.0.0/16", "AS31898", "Oracle Cloud"),
    ("129.155.0.0/16", "AS31898", "Oracle Cloud"),
    ("129.156.0.0/16", "AS31898", "Oracle Cloud"),
    ("129.157.0.0/16", "AS31898", "Oracle Cloud"),
    ("129.158.0.0/16", "AS31898", "Oracle Cloud"),
    ("129.159.0.0/16", "AS31898", "Oracle Cloud"),
    ("130.61.0.0/16", "AS31898", "Oracle Cloud"),
    ("132.145.0.0/16", "AS31898", "Oracle Cloud"),
    ("140.91.0.0/16", "AS31898", "Oracle Cloud"),
    ("147.154.0.0/16", "AS31898", "Oracle Cloud"),
    ("148.163.0.0/16", "AS31898", "Oracle Cloud"),
    ("152.67.0.0/16", "AS31898", "Oracle Cloud"),
    ("155.248.0.0/16", "AS31898", "Oracle Cloud"),
    ("156.151.0.0/16", "AS31898", "Oracle Cloud"),
    ("158.101.0.0/16", "AS31898", "Oracle Cloud"),
    ("168.106.0.0/16", "AS31898", "Oracle Cloud"),
    ("192.29.0.0/16", "AS31898", "Oracle Cloud"),
    # --- Hetzner ---
    ("116.202.0.0/16", "AS24940", "Hetzner"),
    ("116.203.0.0/16", "AS24940", "Hetzner"),
    ("159.69.0.0/16", "AS24940", "Hetzner"),
    ("168.119.0.0/16", "AS24940", "Hetzner"),
    ("188.34.0.0/16", "AS24940", "Hetzner"),
    ("188.40.0.0/16", "AS24940", "Hetzner"),
    ("213.133.0.0/16", "AS24940", "Hetzner"),
    ("23.88.0.0/16", "AS24940", "Hetzner"),
    ("23.97.0.0/16", "AS24940", "Hetzner"),
    ("49.12.0.0/16", "AS24940", "Hetzner"),
    ("49.13.0.0/16", "AS24940", "Hetzner"),
    ("65.21.0.0/16", "AS24940", "Hetzner"),
    ("78.46.0.0/16", "AS24940", "Hetzner"),
    ("88.198.0.0/16", "AS24940", "Hetzner"),
    ("94.130.0.0/16", "AS24940", "Hetzner"),
    ("95.216.0.0/16", "AS24940", "Hetzner"),
    ("135.181.0.0/16", "AS24940", "Hetzner"),
]

_PREFIX_NETWORKS = [(ip_network(prefix), asn, name) for prefix, asn, name in _ASN_ENTRIES]

# ASNs that are shared multi-tenant cloud/hosting/CDN — matches here are weak
# ownership signals (many unrelated customers co-tenant on the same ASN).
CLOUD_ASNS = {
    "AS13335",  # Cloudflare
    "AS16509",  # Amazon AWS
    "AS15169",  # Google Cloud
    "AS8075",   # Microsoft Azure
    "AS20940",  # Akamai
    "AS54113",  # Fastly
    "AS14061",  # DigitalOcean
    "AS63949",  # Linode
    "AS20473",  # Vultr
    "AS16276",  # OVH
    "AS31898",  # Oracle Cloud
    "AS24940",  # Hetzner
}


def resolve_asn(ip_str: str) -> Optional[Dict[str, str]]:
    """Return ``{"asn": ..., "provider": ...}`` for an IP, or None if unknown."""
    try:
        ip = ip_address(ip_str)
    except ValueError:
        return None
    for network, asn, name in _PREFIX_NETWORKS:
        if ip in network:
            return {"asn": asn, "provider": name}
    return None


def is_cloud_asn(asn: Optional[str]) -> bool:
    """True if the ASN is a known shared cloud/hosting/CDN provider."""
    return bool(asn) and asn in CLOUD_ASNS
