"""MCP security: AES-256-GCM encryption and JWKS-based JWT validation."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)


class AES256GCMCipher:
    """AES-256-GCM encryption/decryption for sensitive medical data fields."""

    @staticmethod
    def encrypt_field(plaintext: str, key: bytes) -> str:
        """Encrypt a string field with AES-256-GCM.

        Returns base64-encoded ciphertext with nonce prepended.
        """
        if not isinstance(key, bytes) or len(key) != 32:
            raise ValueError("Key must be 32 bytes (256 bits)")
        aesgcm = AESGCM(key)
        nonce = AESGCM.generate_nonce()
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        # Prepend nonce to ciphertext and base64 encode
        return base64.b64encode(nonce + ciphertext).decode("utf-8")

    @staticmethod
    def decrypt_field(ciphertext_b64: str, key: bytes) -> str:
        """Decrypt a base64-encoded AES-256-GCM encrypted field."""
        if not isinstance(key, bytes) or len(key) != 32:
            raise ValueError("Key must be 32 bytes (256 bits)")
        data = base64.b64decode(ciphertext_b64)
        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")


class MCPJWTAuth:
    """JWKS-based JWT validation for MCP external system tokens.

    Fetches JWKS from the configured endpoint and caches it.
    """

    def __init__(self, jwks_url: str | None = None):
        self._jwks_url = jwks_url
        self._cached_keys: list[dict[str, Any]] | None = None

    async def get_jwks(self) -> list[dict[str, Any]]:
        """Fetch and cache JWKS keys."""
        if self._cached_keys is not None:
            return self._cached_keys

        if not self._jwks_url:
            logger.warning("No JWKS URL configured — MCP JWT validation disabled")
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self._jwks_url)
                resp.raise_for_status()
                data = resp.json()
                self._cached_keys = data.get("keys", [])
                return self._cached_keys
        except Exception as e:
            logger.error("Failed to fetch JWKS from %s: %s", self._jwks_url, e)
            return []

    async def validate_token(self, token: str) -> dict[str, Any] | None:
        """Validate a JWT against cached JWKS keys.

        Returns the decoded payload if valid, None otherwise.
        """
        if not self._jwks_url:
            # No JWKS configured — allow all for development
            return {"sub": "unknown", "iss": "development"}

        keys = await self.get_jwks()
        if not keys:
            return None

        import jwt as pyjwt

        for key_data in keys:
            try:
                # Construct public key from JWKS
                from jwcrypto import jwk
                public_key = jwk.JWK(**key_data)
                key_obj = public_key.export_to_pem()

                payload = pyjwt.decode(
                    token,
                    key_obj,
                    algorithms=["RS256", "ES256"],
                    options={"verify_aud": False},
                )
                return payload
            except Exception:
                continue

        logger.warning("MCP JWT validation failed — no matching key found")
        return None
