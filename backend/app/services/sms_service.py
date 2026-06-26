"""SMS service with pluggable providers and retry support.

Usage:
    provider = get_sms_provider()
    await provider.send(phone, template_params)
"""

from __future__ import annotations

import abc
import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ── Template ───────────────────────────────────────────────────────────

SMS_TEMPLATE = (
    "【用药确认】请确认您已在{time}服用{name}{dosage}。"
    "如已服用，请回复\"是\"；如未服用，请回复\"否\"并尽快补服。感谢配合！"
)


def format_sms(name: str, dosage: str, time: str) -> str:
    """Format the SMS message body with the given parameters."""
    return SMS_TEMPLATE.format(time=time, name=name, dosage=dosage)


# ── Abstract Provider ──────────────────────────────────────────────────


class SMSProvider(abc.ABC):
    """Abstract base class for SMS providers."""

    @abc.abstractmethod
    async def send(self, phone: str, message: str) -> bool:
        """Send an SMS. Returns True on success, False on failure."""
        ...

    @abc.abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        ...


# ── Console Provider (development) ────────────────────────────────────


class ConsoleSMSProvider(SMSProvider):
    """Log SMS to console — for development/testing."""

    def name(self) -> str:
        return "console"

    async def send(self, phone: str, message: str) -> bool:
        logger.info("=" * 50)
        logger.info("[SMS] To: %s", phone)
        logger.info("[SMS] Body: %s", message)
        logger.info("=" * 50)
        return True


# ── Tencent Cloud SMS Provider ─────────────────────────────────────────


class TencentCloudSMSProvider(SMSProvider):
    """Send SMS via Tencent Cloud SMS Gateway.

    Requires the following env settings fully configured:
      TENCENT_SMS_SECRET_ID, TENCENT_SMS_SECRET_KEY,
      TENCENT_SMS_SDK_APP_ID, TENCENT_SMS_SIGN_NAME,
      TENCENT_SMS_TEMPLATE_ID.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._secret_id = settings.tencent_sms_secret_id or ""
        sk = settings.tencent_sms_secret_key
        self._secret_key = sk.get_secret_value() if sk else ""
        self._sdk_app_id = settings.tencent_sms_sdk_app_id or ""
        self._sign_name = settings.tencent_sms_sign_name or ""
        self._template_id = settings.tencent_sms_template_id or ""
        self._region = settings.tencent_sms_region

    def name(self) -> str:
        return "tencent_cloud"

    async def send(self, phone: str, message: str) -> bool:
        """Send SMS via Tencent Cloud template-based SMS.

        The ``message`` is passed as the first template param (``{1}``).
        The Tencent Cloud template should reserve a single variable slot
        for the full reminder text, e.g.: ``{1}``
        """
        try:
            from tencentcloud.common import credential
            from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
                TencentCloudSDKException,
            )
            from tencentcloud.sms.v20210111 import models, sms_client

            cred = credential.Credential(self._secret_id, self._secret_key)
            client = sms_client.SmsClient(cred, self._region)

            # Ensure phone has country code prefix
            if not phone.startswith("+"):
                phone = f"+86{phone}"

            req = models.SendSmsRequest()
            req.PhoneNumberSet = [phone]
            req.SmsSdkAppId = self._sdk_app_id
            req.SignName = self._sign_name
            req.TemplateId = self._template_id
            req.TemplateParamSet = [message]

            resp = client.SendSms(req)

            if resp.SendStatusSet:
                status = resp.SendStatusSet[0]
                if status.Code == "Ok":
                    logger.info(
                        "[TencentSMS] ✓ 发送成功 → %s (sid=%s)",
                        phone, status.SerialNo,
                    )
                    return True

                logger.error(
                    "[TencentSMS] ✗ 发送失败 → %s: %s (code=%s)",
                    phone, status.Message, status.Code,
                )
                return False

            logger.error("[TencentSMS] ✗ 发送失败 → %s: 无返回状态", phone)
            return False

        except TencentCloudSDKException as e:
            logger.error("[TencentSMS] SDK 异常: %s", e, exc_info=True)
            return False
        except Exception as e:
            logger.error("[TencentSMS] 未知异常: %s", e, exc_info=True)
            return False


# ── Provider Factory ──────────────────────────────────────────────────


def get_sms_provider() -> SMSProvider:
    """Return the configured SMS provider.

    If Tencent Cloud SMS env vars are fully configured, returns
    ``TencentCloudSMSProvider``; otherwise falls back to
    ``ConsoleSMSProvider`` for development/testing.
    """
    settings = get_settings()
    if (
        settings.tencent_sms_secret_id
        and settings.tencent_sms_secret_key
        and settings.tencent_sms_sdk_app_id
        and settings.tencent_sms_sign_name
        and settings.tencent_sms_template_id
    ):
        logger.info("[SMS] ── 使用 Tencent Cloud SMS Provider ──")
        return TencentCloudSMSProvider()

    logger.info("[SMS] ── 使用 Console SMS Provider (开发模式) ──")
    return ConsoleSMSProvider()
