"""Attack graph endpoint: correct shape, and query count does not grow per subdomain."""
from datetime import datetime, timezone

from sqlalchemy import event

from app.models.asset import Subdomain
from app.models.port import Port
from app.models.scan import Scan
from app.models.user import User
from app.models.vulnerability import Vulnerability


def _seed(db, email, n=60):
    user = db.query(User).filter(User.email == email).one()
    scan = Scan(domain="example.com", status="completed", created_by=user.id,
                organization_id=user.organization_id, completed_at=datetime.now(timezone.utc))
    db.add(scan)
    db.flush()
    for i in range(n):
        sub = Subdomain(scan_id=scan.id, hostname=f"h{i}.example.com", ip_addresses=["10.0.0.1"], is_alive=True)
        db.add(sub)
        db.flush()
        db.add(Port(subdomain_id=sub.id, port_number=443, state="open", service="https"))
        db.add(Port(subdomain_id=sub.id, port_number=80, state="open", service="http"))
        if i % 10 == 0:
            db.add(Vulnerability(scan_id=scan.id, subdomain_id=sub.id, template_id="t", name="Exposed .git",
                                 severity="high", host=sub.hostname))
    db.commit()
    return scan


def test_graph_shape_and_constant_queries(client, auth_headers, db_session):
    scan = _seed(db_session, auth_headers["email"])
    engine = db_session.get_bind()
    statements = []

    def count(*_a, **_k):
        statements.append(1)

    event.listen(engine, "before_cursor_execute", count)
    try:
        r = client.get("/api/v1/assets/graph", params={"scan_id": scan.id},
                       headers={"Authorization": auth_headers["Authorization"]})
    finally:
        event.remove(engine, "before_cursor_execute", count)

    assert r.status_code == 200, r.text
    body = r.json()
    types = {}
    for n in body["nodes"]:
        types[n["type"]] = types.get(n["type"], 0) + 1
    assert types == {"domain": 1, "subdomain": 60, "port": 120, "vulnerability": 6}
    sub = next(n for n in body["nodes"] if n["label"] == "h0.example.com")
    assert [p["port"] for p in sub["ports"]] == [80, 443]
    assert sub["vuln_count"] == 1
    assert len(body["edges"]) == 60 + 120 + 6
    # Was 2 queries per subdomain (120+); now a handful regardless of size.
    assert len(statements) < 20
