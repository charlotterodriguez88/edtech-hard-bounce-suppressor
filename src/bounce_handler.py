"""Edtech delivery policy: suppress recipients after a hard bounce."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .infrai_client import InfraiClient


HARD_BOUNCE = "hard_bounce"


@dataclass(frozen=True)
class DeliveryEvent:
    event_id: str
    event_type: str
    recipient: str


@dataclass(frozen=True)
class BounceDecision:
    suppressed: bool
    recipient: str


def handle_delivery_event(
    event: DeliveryEvent, client: InfraiClient
) -> BounceDecision:
    """Apply the suppression policy to one normalized delivery event."""
    if event.event_type != HARD_BOUNCE:
        return BounceDecision(suppressed=False, recipient=event.recipient)

    digest = hashlib.sha256(
        f"edtech-hard-bounce:{event.event_id}:{event.recipient}".encode("utf-8")
    ).hexdigest()
    client.add_suppression(
        event.recipient,
        reason=HARD_BOUNCE,
        idempotency_key=f"bounce-{digest}",
    )
    return BounceDecision(suppressed=True, recipient=event.recipient)
