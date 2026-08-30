from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass
class RazorpayStatus:
    enabled: bool
    mode: str
    message: str


def get_razorpay_status() -> RazorpayStatus:
    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")

    if not key_id or not key_secret:
        return RazorpayStatus(
            enabled=False,
            mode="demo",
            message="Razorpay not configured; the app is running in local synthetic-demo mode.",
        )

    return RazorpayStatus(
        enabled=True,
        mode="test_mode",
        message="Razorpay credentials detected; sandbox integration is enabled.",
    )
