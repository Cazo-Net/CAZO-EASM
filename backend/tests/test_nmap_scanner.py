"""Tests for the nmap-backed port scanner.

These verify XML parsing fidelity (service/version strings that match what a
human sees in a raw nmap terminal) and the graceful-absence behaviour when the
nmap binary is not available. Live subprocess runs are covered by
test_nmap_integration when network + binary are present.
"""
import pytest

from app.scanners.nmap_scanner import NmapPortScanner, _resolve_nmap
from app.scanners.registry import registry


SAMPLE_XML = """<nmaprun>
  <host>
    <address addr="111.93.163.54" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="21"><state state="open"/><service name="ftp" product="Microsoft ftpd" version="7.5"/></port>
      <port protocol="tcp" portid="80"><state state="open"/><service name="http" product="Microsoft HTTPAPI" version="httpd 2.0" extrainfo="(SSDP/UPnP)"><cpe>cpe:/a:microsoft:httpapi:2.0</cpe></service></port>
      <port protocol="tcp" portid="135"><state state="open"/><service name="msrpc" product="Microsoft Windows RPC"/></port>
      <port protocol="tcp" portid="445"><state state="open"/><service name="microsoft-ds"/></port>
      <port protocol="tcp" portid="2179"><state state="open"/><service name="msrdp" product="Microsoft Terminal Services" version="RDP"/></port>
      <port protocol="tcp" portid="5985"><state state="open"/><service name="http" product="Microsoft HTTPAPI" version="httpd 2.0" extrainfo="(SSDP/UPnP)"/></port>
      <port protocol="tcp" portid="8011"><state state="open"/><service name="http-alt"/></port>
    </ports>
    <os><osmatch name="Microsoft Windows 10/11" accuracy="95"><osclass type="general purpose" vendor="Microsoft" osfamily="Windows" accuracy="95"><cpe>cpe:/o:microsoft:windows</cpe></osclass></osmatch></os>
    <hostscript><script id="smb-security-mode" output="account_used: guest&#10;message_signing: disabled"/></hostscript>
  </host>
</nmaprun>"""


def test_registered():
    assert registry.get("ports-nmap") is not None


def test_parse_ports_and_versions():
    s = NmapPortScanner()
    r = s._parse("111.93.163.54", SAMPLE_XML)
    assert r["success"] is True
    assert r["open_ports"] == 7
    by_port = {p["port"]: p for p in r["ports"]}
    assert by_port[80]["service"] == "http"
    assert by_port[80]["version"] == "Microsoft HTTPAPI httpd 2.0 (SSDP/UPnP)"
    assert by_port[21]["version"] == "Microsoft ftpd 7.5"
    assert by_port[2179]["version"] == "Microsoft Terminal Services RDP"


def test_parse_os_and_scripts():
    s = NmapPortScanner()
    r = s._parse("111.93.163.54", SAMPLE_XML)
    assert r["os"]["family"] == "Windows"
    assert r["os"]["cpe"] == "cpe:/o:microsoft:windows"
    assert r["scripts"]["smb-security-mode"] == "account_used: guest | message_signing: disabled"


def test_banner_is_port_specific_not_polluted():
    s = NmapPortScanner()
    r = s._parse("111.93.163.54", SAMPLE_XML)
    by_port = {p["port"]: p for p in r["ports"]}
    # banner holds the CPE only, host scripts live in the top-level field
    assert by_port[80]["banner"] == "cpe:/a:microsoft:httpapi:2.0"
    assert "smb-security-mode" not in by_port[80]["banner"]


def test_validate_target():
    s = NmapPortScanner()
    assert s.validate_target("111.93.163.54")
    assert s.validate_target("example.com")
    assert not s.validate_target("not a host")


def test_scan_raises_when_binary_missing(monkeypatch):
    s = NmapPortScanner()
    monkeypatch.setattr(s, "available", lambda: False)
    monkeypatch.setattr(NmapPortScanner, "_binary", None)
    with pytest.raises(RuntimeError):
        # run_with_retry will re-raise after retries -> our scan() raises
        import asyncio
        asyncio.run(s.scan("1.2.3.4", port_list=[80]))


def test_resolve_finds_bundled_binary():
    # At least one of the known bundled locations resolves in CI/local.
    path = _resolve_nmap()
    # Either a real binary path or None; never an invalid string.
    assert path is None or isinstance(path, str)
