"""MCP v1 API endpoints for external HIS system integration."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.mcp.adapters import get_adapter
from app.api.mcp.adapters.default_adapter import DefaultHISAdapter
from app.db.session import get_db
from app.models.mcp import MCPAuditLog, MCPSubscription

router = APIRouter()


async def verify_mcp_auth(
    request: Request,
    authorization: str | None = Header(None, alias="Authorization"),
    x_mcp_version: str | None = Header(None, alias="X-MCP-Version"),
    x_request_id: str | None = Header(None, alias="X-Request-ID"),
):
    """Verify MCP authentication headers."""
    if not x_mcp_version:
        raise HTTPException(status_code=400, detail="Missing X-MCP-Version header")
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    # TODO: In production, validate JWT via MCPJWTAuth with configured JWKS URL
    # For now, accept any valid Bearer token format
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization format")

    # Store request ID for audit logging
    request.state.request_id = x_request_id or str(uuid.uuid4())
    request.state.operation = "mcp_api"


@router.get(
    "/patients/{external_patient_id}/records",
    summary="获取外部系统患者病历",
)
async def get_patient_records(
    external_patient_id: str,
    from_date: str | None = None,
    types: str | None = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_mcp_auth),
):
    """Fetch patient records from an external HIS system via the configured adapter."""
    try:
        adapter = DefaultHISAdapter()
        record_types = types.split(",") if types else None

        result = await adapter.fetch_patient_records(
            external_patient_id=external_patient_id,
            from_date=from_date,
            record_types=record_types,
        )

        # Audit log
        audit = MCPAuditLog(
            operation="fetch_records",
            external_patient_id=external_patient_id,
            status="success",
            created_at=datetime.utcnow(),
        )
        db.add(audit)
        await db.commit()

        return result

    except Exception as e:
        audit = MCPAuditLog(
            operation="fetch_records",
            external_patient_id=external_patient_id,
            status="failed",
            error_message=str(e),
            created_at=datetime.utcnow(),
        )
        db.add(audit)
        await db.commit()

        raise HTTPException(status_code=502, detail=f"External system error: {str(e)}")


@router.post(
    "/clinical/diagnosis",
    summary="推送诊断结论到外部系统",
)
async def push_diagnosis(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_mcp_auth),
):
    """Push a diagnosis conclusion to an external HIS system."""
    body = await request.json()

    external_patient_id = body.get("externalPatientId")
    diagnosis = body.get("diagnosis")
    icd11 = body.get("icd11")
    doctor = body.get("doctor")
    diagnosis_date = body.get("diagnosisDate")
    attachments = body.get("attachments")

    if not external_patient_id or not diagnosis:
        raise HTTPException(status_code=422, detail="Missing required fields: externalPatientId, diagnosis")

    try:
        adapter = DefaultHISAdapter()
        result = await adapter.push_diagnosis(
            external_patient_id=external_patient_id,
            diagnosis=diagnosis,
            icd11_code=icd11,
            doctor_name=doctor,
            diagnosis_date=diagnosis_date,
            attachments=attachments,
        )

        # Audit log
        audit = MCPAuditLog(
            operation="push_diagnosis",
            external_patient_id=external_patient_id,
            request_summary=f"Diagnosis: {diagnosis[:100]}",
            status="success",
            created_at=datetime.utcnow(),
        )
        db.add(audit)
        await db.commit()

        return {"status": "pushed", "external_response": result}

    except Exception as e:
        audit = MCPAuditLog(
            operation="push_diagnosis",
            external_patient_id=external_patient_id,
            status="failed",
            error_message=str(e),
            created_at=datetime.utcnow(),
        )
        db.add(audit)
        await db.commit()

        raise HTTPException(status_code=502, detail=f"Failed to push to external system: {str(e)}")


@router.post(
    "/subscriptions",
    summary="注册外部系统 Webhook",
)
async def create_subscription(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_mcp_auth),
):
    """Register a webhook callback for external system events."""
    body = await request.json()

    callback_url = body.get("callbackUrl")
    events = body.get("events", [])

    if not callback_url:
        raise HTTPException(status_code=422, detail="Missing callbackUrl")

    subscription = MCPSubscription(
        external_system=body.get("externalSystem", "unknown"),
        callback_url=callback_url,
        events=events,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(subscription)
    await db.commit()

    return {
        "subscription_id": str(subscription.id),
        "status": "created",
        "callback_url": callback_url,
        "events": events,
    }
