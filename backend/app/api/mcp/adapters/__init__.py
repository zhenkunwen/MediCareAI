"""HIS adapter registry for MCP external system integration."""

from __future__ import annotations

from typing import Any

_adapter_registry: dict[str, type["BaseHISAdapter"]] = {}


def register_adapter(name: str, adapter_class: type["BaseHISAdapter"]) -> None:
    """Register an adapter class by name."""
    _adapter_registry[name] = adapter_class


def get_adapter(name: str) -> type["BaseHISAdapter"] | None:
    """Get an adapter class by name."""
    return _adapter_registry.get(name)


def list_adapters() -> list[str]:
    """List all registered adapter names."""
    return list(_adapter_registry.keys())


class BaseHISAdapter:
    """Abstract base class for HIS system adapters."""

    name: str = "base"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    async def fetch_patient_records(
        self,
        external_patient_id: str,
        from_date: str | None = None,
        record_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch patient records from the external HIS system."""
        raise NotImplementedError

    async def push_diagnosis(
        self,
        external_patient_id: str,
        diagnosis: str,
        icd11_code: str | None = None,
        doctor_name: str | None = None,
        diagnosis_date: str | None = None,
        attachments: list[str] | None = None,
    ) -> dict[str, Any]:
        """Push a diagnosis conclusion to the external HIS system."""
        raise NotImplementedError

    async def validate_credentials(self) -> bool:
        """Validate that the adapter can connect to the HIS system."""
        raise NotImplementedError
