"""Finding quality: shared catalog, merging, exploit intel, takeover proof."""
from __future__ import annotations

import asyncio

import dns.resolver

from app.scanners.exploit_intel import apply_exploit_intel, enrich_with_exploit_intel
from app.scanners.finding_catalog import apply_catalog, polish_findings
from app.scanners.v2.exposure_validation import ExposureValidator, takeover_signature_for


def _f(tid, sev, host="a.example.com", at=None, source="x", **kw):
    return {"template_id": tid, "name": tid, "severity": sev, "host": host,
            "matched_at": at or f"https://{host}/", "description": "", "tags": [], "source": source, **kw}


# ── Catalog ─────────────────────────────────────────────────────────────────

def test_both_engines_use_the_same_words_for_the_same_issue():
    v1 = apply_catalog(_f("hdr/missing-csp", "medium"))
    v2 = apply_catalog(_f("headers/missing-csp", "low"))
    for k in ("template_id", "name", "severity", "vuln_type"):
        assert v1[k] == v2[k]
    assert v1["template_id"] == "header/missing-csp"
    assert "Fix:" in v1["description"] and "Why it matters:" in v1["description"]
    assert v1["reference"] and "CWE-1021" in v1["tags"]


def test_dkim_not_found_is_informational_not_a_vulnerability():
    f = apply_catalog(_f("dns/missing-dkim", "medium"))
    assert f["severity"] == "info"
    assert "common selectors" in f["name"]


def test_unknown_findings_pass_through():
    f = _f("web/some-new-check", "high")
    assert apply_catalog(f)["template_id"] == "web/some-new-check"
    assert apply_catalog(f)["severity"] == "high"


def test_takeover_keeps_the_checks_severity():
    f = apply_catalog(_f("exposure-validation/subdomain_takeover", "medium", description="x Fix: y"))
    assert f["severity"] == "medium" and f["template_id"] == "dns/subdomain-takeover"


# ── Merging ─────────────────────────────────────────────────────────────────

def test_same_issue_from_two_checkers_is_merged_with_both_sources():
    out = polish_findings([
        _f("exposure-validation/security_headers/strict-transport-security", "medium",
           at="https://a.example.com", source="exposure-validation", extracted_results=["no header"]),
        _f("headers/missing-hsts", "medium", at="https://a.example.com/", source="web-exposure",
           extracted_results=["HTTP 200"]),
        _f("headers/missing-hsts", "medium", host="b.example.com", source="web-exposure"),
    ])
    assert len(out) == 2
    a = next(f for f in out if f["host"] == "a.example.com")
    assert set(a["sources"]) == {"exposure-validation", "web-exposure"}
    assert {"found-by:web-exposure", "found-by:exposure-validation"} <= set(a["tags"])
    assert a["extracted_results"] == ["no header", "HTTP 200"]


def test_path_findings_on_different_paths_stay_separate():
    out = polish_findings([
        _f("web/exposed-git", "high", at="https://a.example.com/.git/HEAD"),
        _f("web/exposed-git", "high", at="https://a.example.com/app/.git/HEAD"),
        _f("web/exposed-git", "high", at="https://a.example.com/.git/HEAD/"),
    ])
    assert len(out) == 2


def test_most_severe_copy_wins():
    out = polish_findings([_f("web/x", "low"), _f("web/x", "critical")])
    assert len(out) == 1 and out[0]["severity"] == "critical"


# ── Exploit intel (KEV / EPSS) ──────────────────────────────────────────────

def _cve(cve, sev="medium"):
    return {"template_id": f"cve-correlation/{cve}", "name": f"nginx 1.18 — {cve}", "severity": sev,
            "host": "a.example.com", "cve_id": cve, "tags": ["cve"], "reference": [], "description": "d"}


def test_kev_raises_severity_and_explains_why():
    fs = [_cve("CVE-2021-23017"), _cve("CVE-2020-0001", "low")]
    kev = {"CVE-2021-23017": {"cveID": "CVE-2021-23017", "dateAdded": "2023-01-01",
                              "knownRansomwareCampaignUse": "Known", "requiredAction": "Apply updates."}}
    epss = {"CVE-2020-0001": {"epss": 0.02, "percentile": 0.4}}
    assert apply_exploit_intel(fs, kev, epss) == 2
    assert fs[0]["severity"] == "critical"
    assert {"known-exploited", "cisa-kev", "ransomware"} <= set(fs[0]["tags"])
    assert any("CISA KEV" in e for e in fs[0]["extracted_results"])
    assert "Apply updates." in fs[0]["description"]
    assert fs[1]["severity"] == "low" and fs[1]["epss"] == 0.02


def test_high_epss_raises_to_high_but_never_lowers():
    fs = [_cve("CVE-2023-1111", "medium"), _cve("CVE-2023-2222", "critical")]
    epss = {c: {"epss": 0.9, "percentile": 0.99} for c in ("CVE-2023-1111", "CVE-2023-2222")}
    apply_exploit_intel(fs, {}, epss)
    assert [f["severity"] for f in fs] == ["high", "critical"]


def test_enrichment_never_fails_the_scan(monkeypatch):
    import app.services.threat_intel as ti

    def boom(*a, **k):
        raise RuntimeError("feed down")

    monkeypatch.setattr(ti, "kev_catalog", boom)
    fs = [_cve("CVE-2021-23017")]
    status = asyncio.run(enrich_with_exploit_intel(fs))
    assert status.startswith("skipped")
    assert fs[0]["severity"] == "medium"


def test_no_cves_means_no_network():
    assert asyncio.run(enrich_with_exploit_intel([_f("web/x", "low")])) == "ok (no CVE findings)"


# ── Subdomain takeover needs real proof ────────────────────────────────────

def test_signature_matching():
    assert takeover_signature_for("foo.github.io.").service == "GitHub Pages"
    assert takeover_signature_for("bucket.s3.eu-west-1.amazonaws.com").service == "AWS S3"
    assert takeover_signature_for("x.azurewebsites.net").nxdomain_means_unclaimed
    assert takeover_signature_for("d123.cloudfront.net") is None  # no longer claimable
    assert takeover_signature_for("notgithub.io") is None


class _Ans(list):
    pass


class _R:
    def __init__(self, t):
        self.target = t


def _scanner_with(monkeypatch, cname, page, nx=False):
    def fake_resolve(name, rtype="A", *a, **k):
        if rtype == "CNAME":
            return _Ans([_R(cname + ".")])
        if nx:
            raise dns.resolver.NXDOMAIN()
        return _Ans(["1.2.3.4"])

    monkeypatch.setattr(dns.resolver, "resolve", fake_resolve)
    sc = ExposureValidator()

    async def page_fn(host):
        return page.lower()

    monkeypatch.setattr(sc, "_fetch_takeover_page", page_fn)
    return sc


def test_generic_404_is_not_a_takeover(monkeypatch):
    sc = _scanner_with(monkeypatch, "foo.github.io", "<h1>404 Not Found</h1> page not found")
    assert asyncio.run(sc._check_subdomain_takeover(["docs.example.com"])) == []


def test_service_specific_page_confirms_takeover(monkeypatch):
    sc = _scanner_with(monkeypatch, "foo.github.io", "There isn't a GitHub Pages site here.")
    out = asyncio.run(sc._check_subdomain_takeover(["docs.example.com"]))
    assert len(out) == 1
    assert out[0]["severity"] == "high"
    assert any("unclaimed" in e for e in out[0]["details"]["evidence"])


def test_s3_fingerprint_matches_regardless_of_case(monkeypatch):
    sc = _scanner_with(monkeypatch, "b.s3.amazonaws.com", "<Code>NoSuchBucket</Code>")
    assert len(asyncio.run(sc._check_subdomain_takeover(["files.example.com"]))) == 1


def test_azure_nxdomain_target_confirms_takeover(monkeypatch):
    sc = _scanner_with(monkeypatch, "old-app.azurewebsites.net", "", nx=True)
    out = asyncio.run(sc._check_subdomain_takeover(["app.example.com"]))
    assert len(out) == 1 and "NXDOMAIN" in " ".join(out[0]["details"]["evidence"])
