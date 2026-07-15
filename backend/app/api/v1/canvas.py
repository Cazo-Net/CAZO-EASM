from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, List
import json

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.canvas import Canvas, CanvasNode, CanvasEdge
from app.models.scan import Scan
from app.models.asset import Subdomain
from app.models.port import Port
from app.models.ssl import SSLCertificate
from app.models.dns import DNSRecord
from app.models.technology import Technology
from app.models.vulnerability import Vulnerability
from app.schemas.canvas import (
    CanvasCreate, CanvasUpdate, CanvasResponse, CanvasDetailResponse,
    CanvasNodeCreate, CanvasNodeUpdate, CanvasNodeResponse,
    CanvasEdgeCreate, CanvasEdgeResponse,
    CanvasImportRequest, CanvasBulkNodeCreate,
    ScanAssetPreview, ScanPreviewResponse,
)

router = APIRouter()

RISK_COLORS = {
    "critical": "#EF4444",
    "high": "#F97316",
    "medium": "#F59E0B",
    "low": "#3B82F6",
    "informational": "#6B7280",
}

ASSET_ICONS = {
    "domain": "Globe",
    "subdomain": "Globe",
    "ip_address": "Server",
    "port": "Server",
    "ssl_certificate": "Lock",
    "dns_record": "Network",
    "technology": "Cpu",
    "vulnerability": "Bug",
    "organization": "Building",
    "email": "Mail",
    "cloud_asset": "Cloud",
    "web_application": "Globe",
    "external_service": "ExternalLink",
}


def get_risk_for_asset(db: Session, asset_type: str, asset_id: str) -> str:
    try:
        if asset_type == "vulnerability" and asset_id:
            vuln = db.query(Vulnerability).filter(Vulnerability.id == asset_id).first()
            if vuln:
                return vuln.severity or "informational"
        if asset_type in ("subdomain", "domain") and asset_id:
            sub = db.query(Subdomain).filter(Subdomain.id == asset_id).first()
            if sub and not sub.is_alive:
                return "low"
    except Exception:
        pass
    return "informational"


# ==================== CANVASES ====================

@router.post("", response_model=CanvasResponse)
def create_canvas(data: CanvasCreate, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    canvas = Canvas(
        name=data.name,
        description=data.description,
        user_id=current_user.id,
        project_id=data.project_id,
    )
    db.add(canvas)
    db.commit()
    db.refresh(canvas)
    return CanvasResponse(
        id=canvas.id, name=canvas.name, description=canvas.description,
        user_id=canvas.user_id, project_id=canvas.project_id,
        viewport_x=canvas.viewport_x, viewport_y=canvas.viewport_y,
        viewport_zoom=canvas.viewport_zoom,
        node_count=0, edge_count=0,
        created_at=canvas.created_at, updated_at=canvas.updated_at,
    )


@router.get("", response_model=List[CanvasResponse])
def list_canvases(
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Canvas).filter(Canvas.user_id == current_user.id)
    if project_id:
        q = q.filter(Canvas.project_id == project_id)
    canvases = q.order_by(Canvas.updated_at.desc()).all()
    result = []
    for c in canvases:
        result.append(CanvasResponse(
            id=c.id, name=c.name, description=c.description,
            user_id=c.user_id, project_id=c.project_id,
            viewport_x=c.viewport_x, viewport_y=c.viewport_y,
            viewport_zoom=c.viewport_zoom,
            node_count=len(c.nodes), edge_count=len(c.edges),
            created_at=c.created_at, updated_at=c.updated_at,
        ))
    return result


@router.get("/{canvas_id}", response_model=CanvasDetailResponse)
def get_canvas(canvas_id: str, db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
    canvas = db.query(Canvas).filter(
        Canvas.id == canvas_id, Canvas.user_id == current_user.id
    ).first()
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")
    return CanvasDetailResponse(
        id=canvas.id, name=canvas.name, description=canvas.description,
        user_id=canvas.user_id, project_id=canvas.project_id,
        viewport_x=canvas.viewport_x, viewport_y=canvas.viewport_y,
        viewport_zoom=canvas.viewport_zoom,
        nodes=[CanvasNodeResponse.model_validate(n) for n in canvas.nodes],
        edges=[CanvasEdgeResponse.model_validate(e) for e in canvas.edges],
        created_at=canvas.created_at, updated_at=canvas.updated_at,
    )


@router.put("/{canvas_id}", response_model=CanvasResponse)
def update_canvas(canvas_id: str, data: CanvasUpdate, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    canvas = db.query(Canvas).filter(
        Canvas.id == canvas_id, Canvas.user_id == current_user.id
    ).first()
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")
    if data.name is not None:
        canvas.name = data.name
    if data.description is not None:
        canvas.description = data.description
    if data.viewport_x is not None:
        canvas.viewport_x = data.viewport_x
    if data.viewport_y is not None:
        canvas.viewport_y = data.viewport_y
    if data.viewport_zoom is not None:
        canvas.viewport_zoom = data.viewport_zoom
    db.commit()
    db.refresh(canvas)
    return CanvasResponse(
        id=canvas.id, name=canvas.name, description=canvas.description,
        user_id=canvas.user_id, project_id=canvas.project_id,
        viewport_x=canvas.viewport_x, viewport_y=canvas.viewport_y,
        viewport_zoom=canvas.viewport_zoom,
        node_count=len(canvas.nodes), edge_count=len(canvas.edges),
        created_at=canvas.created_at, updated_at=canvas.updated_at,
    )


@router.delete("/{canvas_id}")
def delete_canvas(canvas_id: str, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    canvas = db.query(Canvas).filter(
        Canvas.id == canvas_id, Canvas.user_id == current_user.id
    ).first()
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")
    db.delete(canvas)
    db.commit()
    return {"ok": True}


# ==================== NODES ====================

@router.post("/{canvas_id}/nodes", response_model=CanvasNodeResponse)
def add_node(canvas_id: str, data: CanvasNodeCreate, db: Session = Depends(get_db),
             current_user: User = Depends(get_current_user)):
    canvas = db.query(Canvas).filter(
        Canvas.id == canvas_id, Canvas.user_id == current_user.id
    ).first()
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")
    risk = get_risk_for_asset(db, data.asset_type, data.asset_id)
    node = CanvasNode(
        canvas_id=canvas_id,
        asset_type=data.asset_type,
        asset_id=data.asset_id,
        label=data.label,
        x=data.x, y=data.y,
        width=data.width, height=data.height,
        color=data.color or RISK_COLORS.get(risk, "#6B7280"),
        icon=data.icon or ASSET_ICONS.get(data.asset_type, "Circle"),
        risk_level=risk,
        data_json=data.data_json,
        notes=data.notes,
        tags=data.tags,
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return CanvasNodeResponse.model_validate(node)


@router.post("/{canvas_id}/nodes/bulk")
def bulk_add_nodes(canvas_id: str, data: CanvasBulkNodeCreate,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    canvas = db.query(Canvas).filter(
        Canvas.id == canvas_id, Canvas.user_id == current_user.id
    ).first()
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")

    node_id_map = {}
    created_nodes = []

    for nd in data.nodes:
        risk = get_risk_for_asset(db, nd.asset_type, nd.asset_id)
        node = CanvasNode(
            canvas_id=canvas_id,
            asset_type=nd.asset_type,
            asset_id=nd.asset_id,
            label=nd.label,
            x=nd.x, y=nd.y,
            width=nd.width, height=nd.height,
            color=nd.color or RISK_COLORS.get(risk, "#6B7280"),
            icon=nd.icon or ASSET_ICONS.get(nd.asset_type, "Circle"),
            risk_level=risk,
            data_json=nd.data_json,
            notes=nd.notes,
            tags=nd.tags,
        )
        db.add(node)
        db.flush()
        node_id_map[nd.asset_id or nd.label] = node.id
        created_nodes.append(node)

    for ed in data.edges:
        source_id = node_id_map.get(ed.source_node_id, ed.source_node_id)
        target_id = node_id_map.get(ed.target_node_id, ed.target_node_id)
        if source_id and target_id:
            edge = CanvasEdge(
                canvas_id=canvas_id,
                source_node_id=source_id,
                target_node_id=target_id,
                label=ed.label,
                edge_type=ed.edge_type,
                animated=ed.animated,
                style_json=ed.style_json,
            )
            db.add(edge)

    db.commit()
    return {"ok": True, "nodes_created": len(created_nodes)}


@router.put("/{canvas_id}/nodes/{node_id}", response_model=CanvasNodeResponse)
def update_node(canvas_id: str, node_id: str, data: CanvasNodeUpdate,
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    node = db.query(CanvasNode).filter(
        CanvasNode.id == node_id, CanvasNode.canvas_id == canvas_id
    ).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(node, field, value)
    db.commit()
    db.refresh(node)
    return CanvasNodeResponse.model_validate(node)


@router.delete("/{canvas_id}/nodes/{node_id}")
def delete_node(canvas_id: str, node_id: str, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    node = db.query(CanvasNode).filter(
        CanvasNode.id == node_id, CanvasNode.canvas_id == canvas_id
    ).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    db.query(CanvasEdge).filter(
        (CanvasEdge.source_node_id == node_id) | (CanvasEdge.target_node_id == node_id),
        CanvasEdge.canvas_id == canvas_id,
    ).delete()
    db.delete(node)
    db.commit()
    return {"ok": True}


# ==================== EDGES ====================

@router.post("/{canvas_id}/edges", response_model=CanvasEdgeResponse)
def add_edge(canvas_id: str, data: CanvasEdgeCreate, db: Session = Depends(get_db),
             current_user: User = Depends(get_current_user)):
    canvas = db.query(Canvas).filter(
        Canvas.id == canvas_id, Canvas.user_id == current_user.id
    ).first()
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")
    edge = CanvasEdge(
        canvas_id=canvas_id,
        source_node_id=data.source_node_id,
        target_node_id=data.target_node_id,
        label=data.label,
        edge_type=data.edge_type,
        animated=data.animated,
        style_json=data.style_json,
    )
    db.add(edge)
    db.commit()
    db.refresh(edge)
    return CanvasEdgeResponse.model_validate(edge)


@router.delete("/{canvas_id}/edges/{edge_id}")
def delete_edge(canvas_id: str, edge_id: str, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    edge = db.query(CanvasEdge).filter(
        CanvasEdge.id == edge_id, CanvasEdge.canvas_id == canvas_id
    ).first()
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")
    db.delete(edge)
    db.commit()
    return {"ok": True}


# ==================== SCAN PREVIEW (for table import UI) ====================

@router.get("/scan/{scan_id}/preview")
def preview_scan_assets(
    scan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all assets from a scan grouped by type for the table import UI."""
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    assets: dict[str, list[ScanAssetPreview]] = {
        "subdomains": [], "ports": [], "ssl_certificates": [],
        "dns_records": [], "technologies": [], "vulnerabilities": [],
    }

    subdomains = db.query(Subdomain).filter(Subdomain.scan_id == scan_id).all()
    for sub in subdomains:
        assets["subdomains"].append(ScanAssetPreview(
            asset_type="subdomain", asset_id=sub.id, label=sub.hostname,
            detail={"ip_addresses": sub.ip_addresses or []},
            is_alive=sub.is_alive,
            risk_level="low" if not sub.is_alive else "informational",
        ))
        ports = db.query(Port).filter(Port.subdomain_id == sub.id).all()
        for port in ports:
            svc = port.service or "unknown"
            assets["ports"].append(ScanAssetPreview(
                asset_type="port", asset_id=port.id,
                label=f"{port.port_number}/{svc}",
                detail={"port": port.port_number, "service": svc, "version": port.version or "", "state": port.state or ""},
                risk_level="high" if svc in ("ssh", "rdp", "ftp", "telnet") else "medium" if svc in ("http", "https") else "informational",
            ))
        ssl_certs = db.query(SSLCertificate).filter(SSLCertificate.subdomain_id == sub.id).all()
        for cert in ssl_certs:
            assets["ssl_certificates"].append(ScanAssetPreview(
                asset_type="ssl_certificate", asset_id=cert.id,
                label=f"{sub.hostname} ({cert.grade or 'N/A'})",
                detail={"issuer": cert.issuer or "", "grade": cert.grade or "", "valid": cert.is_valid, "expiry": str(cert.not_after or "")},
                risk_level="high" if not cert.is_valid else "medium" if cert.grade in ("C", "D", "F") else "low",
            ))
        dns_records = db.query(DNSRecord).filter(DNSRecord.subdomain_id == sub.id).all()
        for dns in dns_records:
            assets["dns_records"].append(ScanAssetPreview(
                asset_type="dns_record", asset_id=dns.id,
                label=f"{dns.record_type}: {dns.value[:60]}",
                detail={"type": dns.record_type, "value": dns.value, "ttl": dns.ttl},
                risk_level="informational",
            ))
        techs = db.query(Technology).filter(Technology.subdomain_id == sub.id).all()
        for tech in techs:
            assets["technologies"].append(ScanAssetPreview(
                asset_type="technology", asset_id=tech.id,
                label=f"{tech.name} {tech.version or ''}".strip(),
                detail={"category": tech.category or "", "version": tech.version or ""},
                risk_level="informational",
            ))

    vulns = db.query(Vulnerability).filter(Vulnerability.scan_id == scan_id).all()
    for v in vulns:
        assets["vulnerabilities"].append(ScanAssetPreview(
            asset_type="vulnerability", asset_id=v.id,
            label=f"[{v.severity.upper()}] {v.name[:60]}",
            detail={"severity": v.severity, "description": v.description or "", "host": v.host or "", "type": v.vuln_type or ""},
            risk_level=v.severity or "informational",
        ))

    counts = {k: len(v) for k, v in assets.items()}

    return ScanPreviewResponse(
        scan_id=scan.id, domain=scan.domain,
        status=scan.status if isinstance(scan.status, str) else scan.status.value,
        assets=assets, counts=counts,
    )


# ==================== IMPORT FROM SCAN ====================

@router.post("/{canvas_id}/import")
def import_scan_to_canvas(canvas_id: str, data: CanvasImportRequest,
                          db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    canvas = db.query(Canvas).filter(
        Canvas.id == canvas_id, Canvas.user_id == current_user.id
    ).first()
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")

    scan = db.query(Scan).filter(Scan.id == data.scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    selected_ids = set(data.asset_ids) if data.asset_ids else None
    selected_types = set(data.asset_types) if data.asset_types else None

    def should_include(asset_type: str, asset_id: str | None = None) -> bool:
        if selected_types and asset_type not in selected_types:
            return False
        if selected_ids and asset_id and asset_id not in selected_ids:
            return False
        if selected_ids and not asset_id:
            return True
        return True

    subdomains = db.query(Subdomain).filter(Subdomain.scan_id == data.scan_id).all()

    nodes_data = []
    edges_data = []

    domain_node_id = f"domain_{scan.domain}"
    nodes_data.append(CanvasNodeCreate(
        asset_type="domain", asset_id=None, label=scan.domain,
        x=400, y=50, data_json={"scan_id": scan.id},
    ))

    ip_map = {}
    x_offset = 100
    y_offset = 200

    for i, sub in enumerate(subdomains):
        sx = x_offset + (i % 5) * 250
        sy = y_offset + (i // 5) * 150
        sub_node_key = sub.id

        if should_include("subdomain", sub.id):
            nodes_data.append(CanvasNodeCreate(
                asset_type="subdomain", asset_id=sub.id, label=sub.hostname,
                x=sx, y=sy, data_json={"ip_addresses": sub.ip_addresses, "is_alive": sub.is_alive},
            ))
            edges_data.append(CanvasEdgeCreate(
                source_node_id=domain_node_id, target_node_id=sub_node_key,
                label="subdomain", edge_type="default",
            ))

        for ip in (sub.ip_addresses or []):
            if ip not in ip_map:
                ip_node_key = f"ip_{ip}"
                ip_map[ip] = ip_node_key
                if should_include("ip_address", None):
                    nodes_data.append(CanvasNodeCreate(
                        asset_type="ip_address", asset_id=None, label=ip,
                        x=sx + 120, y=sy + 80, data_json={"ip": ip},
                    ))
            if should_include("subdomain", sub.id):
                edges_data.append(CanvasEdgeCreate(
                    source_node_id=sub_node_key, target_node_id=ip_map[ip],
                    label="resolves to", edge_type="default",
                ))

        if should_include("port", None):
            ports = db.query(Port).filter(Port.subdomain_id == sub.id).all()
            for port in ports:
                if selected_ids and port.id not in selected_ids:
                    continue
                port_node_key = f"port_{port.id}"
                nodes_data.append(CanvasNodeCreate(
                    asset_type="port", asset_id=port.id,
                    label=f"{port.port_number}/{port.service or 'unknown'}",
                    x=sx + 250, y=sy + 60,
                    data_json={"port": port.port_number, "service": port.service, "version": port.version},
                ))
                edges_data.append(CanvasEdgeCreate(
                    source_node_id=sub_node_key, target_node_id=port_node_key,
                    label="open port", edge_type="default",
                ))

        if should_include("ssl_certificate", None):
            ssl_certs = db.query(SSLCertificate).filter(SSLCertificate.subdomain_id == sub.id).all()
            for cert in ssl_certs:
                if selected_ids and cert.id not in selected_ids:
                    continue
                cert_node_key = f"ssl_{cert.id}"
                nodes_data.append(CanvasNodeCreate(
                    asset_type="ssl_certificate", asset_id=cert.id,
                    label=f"SSL: {sub.hostname}",
                    x=sx - 50, y=sy + 100,
                    data_json={"issuer": cert.issuer, "grade": cert.grade, "valid": cert.is_valid},
                ))
                edges_data.append(CanvasEdgeCreate(
                    source_node_id=sub_node_key, target_node_id=cert_node_key,
                    label="certificate", edge_type="default",
                ))

        if should_include("technology", None):
            techs = db.query(Technology).filter(Technology.subdomain_id == sub.id).all()
            for tech in techs:
                if selected_ids and tech.id not in selected_ids:
                    continue
                tech_node_key = f"tech_{tech.id}"
                nodes_data.append(CanvasNodeCreate(
                    asset_type="technology", asset_id=tech.id,
                    label=tech.name,
                    x=sx + 50, y=sy + 150,
                    data_json={"category": tech.category, "version": tech.version},
                ))
                edges_data.append(CanvasEdgeCreate(
                    source_node_id=sub_node_key, target_node_id=tech_node_key,
                    label="uses", edge_type="default",
                ))

        if should_include("dns_record", None):
            dns_records = db.query(DNSRecord).filter(DNSRecord.subdomain_id == sub.id).all()
            for dns in dns_records:
                if selected_ids and dns.id not in selected_ids:
                    continue
                dns_node_key = f"dns_{dns.id}"
                nodes_data.append(CanvasNodeCreate(
                    asset_type="dns_record", asset_id=dns.id,
                    label=f"{dns.record_type}: {dns.value[:40]}",
                    x=sx - 100, y=sy + 50,
                    data_json={"type": dns.record_type, "value": dns.value, "ttl": dns.ttl},
                ))
                edges_data.append(CanvasEdgeCreate(
                    source_node_id=sub_node_key, target_node_id=dns_node_key,
                    label="dns", edge_type="default",
                ))

    if should_include("vulnerability", None):
        vulns = db.query(Vulnerability).filter(Vulnerability.scan_id == data.scan_id).all()
        for v in vulns:
            if selected_ids and v.id not in selected_ids:
                continue
            vuln_node_key = f"vuln_{v.id}"
            nodes_data.append(CanvasNodeCreate(
                asset_type="vulnerability", asset_id=v.id,
                label=f"[{v.severity.upper()}] {v.name[:50]}",
                x=400, y=700,
                data_json={"severity": v.severity, "host": v.host or "", "description": v.description or ""},
            ))

    bulk = CanvasBulkNodeCreate(nodes=nodes_data, edges=edges_data)

    node_id_map = {}
    created_count = 0

    for nd in bulk.nodes:
        risk = get_risk_for_asset(db, nd.asset_type, nd.asset_id)
        node = CanvasNode(
            canvas_id=canvas_id,
            asset_type=nd.asset_type,
            asset_id=nd.asset_id,
            label=nd.label,
            x=nd.x, y=nd.y,
            width=nd.width, height=nd.height,
            color=nd.color or RISK_COLORS.get(risk, "#6B7280"),
            icon=nd.icon or ASSET_ICONS.get(nd.asset_type, "Circle"),
            risk_level=risk,
            data_json=nd.data_json,
            notes=nd.notes,
            tags=nd.tags,
        )
        db.add(node)
        db.flush()
        node_id_map[nd.asset_id or nd.label] = node.id
        created_count += 1

    for ed in bulk.edges:
        source_id = node_id_map.get(ed.source_node_id, ed.source_node_id)
        target_id = node_id_map.get(ed.target_node_id, ed.target_node_id)
        if source_id and target_id:
            edge = CanvasEdge(
                canvas_id=canvas_id,
                source_node_id=source_id,
                target_node_id=target_id,
                label=ed.label,
                edge_type=ed.edge_type,
                animated=ed.animated,
                style_json=ed.style_json,
            )
            db.add(edge)

    db.commit()
    return {"ok": True, "nodes_created": created_count, "edges_created": len(bulk.edges)}


# ==================== EXPORT ====================

@router.get("/{canvas_id}/export")
def export_canvas(canvas_id: str, format: str = Query("json"),
                  db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    canvas = db.query(Canvas).filter(
        Canvas.id == canvas_id, Canvas.user_id == current_user.id
    ).first()
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")

    data = {
        "name": canvas.name,
        "description": canvas.description,
        "viewport": {"x": canvas.viewport_x, "y": canvas.viewport_y, "zoom": canvas.viewport_zoom},
        "nodes": [
            {
                "id": n.id, "asset_type": n.asset_type, "asset_id": n.asset_id,
                "label": n.label, "x": n.x, "y": n.y,
                "width": n.width, "height": n.height,
                "color": n.color, "icon": n.icon, "risk_level": n.risk_level,
                "data": n.data_json, "notes": n.notes, "tags": n.tags,
            }
            for n in canvas.nodes
        ],
        "edges": [
            {
                "id": e.id, "source": e.source_node_id, "target": e.target_node_id,
                "label": e.label, "type": e.edge_type, "animated": e.animated,
            }
            for e in canvas.edges
        ],
    }

    if format == "json":
        return JSONResponse(content=data)

    return JSONResponse(content=data)
