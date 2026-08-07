"""Runnable entry point for a normalized email delivery event."""

from __future__ import annotations

import argparse
import json

from src.bounce_handler import DeliveryEvent, handle_delivery_event
from src.infrai_client import InfraiClient


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply the edtech email suppression policy to a delivery event."
    )
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--event-type", required=True, choices=["hard_bounce", "delivered"])
    parser.add_argument("--recipient", required=True)
    args = parser.parse_args()

    event = DeliveryEvent(
        event_id=args.event_id,
        event_type=args.event_type,
        recipient=args.recipient,
    )
    decision = handle_delivery_event(event, InfraiClient())
    print(json.dumps({"suppressed": decision.suppressed, "recipient": decision.recipient}))


if __name__ == "__main__":
    main()
