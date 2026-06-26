"""Default REST-based HIS adapter implementation."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.api.mcp.adapters import BaseHISAdapter, register_adapter

logger = logging.getLogger(__name__)


class DefaultHISAdapter(BaseHISAdapter):
    """Generic REST adapter for HIS integration.

    Reads endpoint templates and auth config from adapter config dict.
    """

    name = "default"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.base_url = (config or {}).get("base_url", "")
        self.api_key = (config or {}).get("api_key", "")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def fetch_patient_records(
        self,
        external_patient_id: str,
        from_date: str | None = None,
        record_types: list[str] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/patients/{external_patient_id}/records"
        params = {}
        if from_date:
            params["from"] = from_date
        if record_types:
            params["types"] = ",".join(record_types)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, headers=self._headers(), params=params)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("HIS fetch failed: %s %s", e.response.status_code, e.response.text)
            raise
        except httpx.RequestError as e:
            logger.error("HIS connection failed: %s", e)
            raise

    async def push_diagnosis(
        self,
        external_patient_id: str,
        diagnosis: str,
        icd11_code: str | None = None,
        doctor_name: str | None = None,
        diagnosis_date: str | None = None,
        attachments: list[str] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/clinical/diagnosis"
        body = {
            "externalPatientId": external_patient_id,
            "diagnosis": diagnosis,
            "icd11": icd11_code,
            "doctor": doctor_name,
            "diagnosisDate": diagnosis_date,
            "attachments": attachments or [],
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=self._headers(), json=body)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("HIS push failed: %s %s", e.response.status_code, e.response.text)
            raise
        except httpx.RequestError as e:
            logger.error("HIS connection failed: %s", e)
            raise

    async def validate_credentials(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/health",
                    headers=self._headers(),
                )
                return resp.status_code == 200
        except Exception:
            return False


# Register the default adapter
register_adapter("default", DefaultHISAdapter)
