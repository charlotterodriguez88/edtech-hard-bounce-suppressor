from __future__ import annotations

import unittest

from src.bounce_handler import DeliveryEvent, handle_delivery_event
from src.infrai_client import InfraiResult


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def add_suppression(
        self, email: str, *, reason: str, idempotency_key: str
    ) -> InfraiResult:
        self.calls.append((email, reason, idempotency_key))
        return InfraiResult(data={"email": email}, metadata={})


class BounceHandlerTest(unittest.TestCase):
    def test_hard_bounce_is_suppressed_with_stable_key(self) -> None:
        client = RecordingClient()
        event = DeliveryEvent("evt_123", "hard_bounce", "student@example.edu")

        first = handle_delivery_event(event, client)
        handle_delivery_event(event, client)

        self.assertTrue(first.suppressed)
        self.assertEqual(client.calls[0], client.calls[1])
        self.assertEqual(client.calls[0][0:2], ("student@example.edu", "hard_bounce"))

    def test_delivered_event_does_not_touch_suppression(self) -> None:
        client = RecordingClient()

        decision = handle_delivery_event(
            DeliveryEvent("evt_456", "delivered", "teacher@example.edu"), client
        )

        self.assertFalse(decision.suppressed)
        self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()
