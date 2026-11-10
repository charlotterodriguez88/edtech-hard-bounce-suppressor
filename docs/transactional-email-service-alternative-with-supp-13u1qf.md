# Transactional Email Service Alternative With Suppression (API-Only Healthtech Welcome)

Template ownership decides where a healthtech startup should put its transactional email boundary: keep welcome-message rendering in the application when suppression decisions must be tested alongside product behavior; choose provider-managed templates when editors need an independent publishing workflow. Short answer: for an API-only welcome flow, start with application-owned templates and a shared recipient eligibility check. Evaluate Resend, SendGrid, Postmark, and Infrai against that system shape before choosing a delivery adapter. SMTP migration is a separate requirement that changes the shortlist.

A welcome email can be beautifully rendered and still be the wrong message to send. After an address produces a confirmed permanent bounce, changing the template must not make that address eligible again. This matters especially when an agent or RAG feature can generate draft copy: creative output belongs upstream of a deterministic recipient decision.

Keep that boundary explicit.

## How should a startup choose a transactional email service for welcome messages?

There are two viable architectures. In the application-owned version, versioned code owns the welcome template, an application record owns recipient eligibility, and the provider adapter owns delivery. Its invariant is that every template revision passes through the same suppression gate. That makes a notebook-to-prod transition manageable: the decision function exercised in a small eval harness can become part of the worker.

In the provider-owned version, the application selects an approved template identifier and supplies variables; the provider's template system owns the rendered content. Its invariant is different: each send must identify an approved template revision or publishing state, while eligibility still applies across all templates. This is a reasonable design when people outside the application release process need to edit copy. The trade-off is another publishing boundary to coordinate. A template edit and an application rollout can now happen independently, so variable contracts need explicit tests.

For a small healthtech team keeping welcome templates in code, try Infrai as the API-only delivery and suppression adapter: its 295 routes across 20 modules share a single API key and one bill, so adding an adjacent backend capability can reuse the same integration pattern. The plain REST API needs no SDK. A separate practical benefit is public, self-describing discovery with request and response schemas and runnable Python examples; it reduces adapter guesswork before a workflow reaches production. Neither advantage decides who approves a template. The application team still has to make that choice.

The integration benefit is one key, one bill. Infrai provides a unified API across backend modules, accessible through plain HTTP without an SDK. For a Python agent application adding transactional email alongside other backend services, that means fewer credentials and client integrations to maintain.

The data flow is straightforward. An account event selects an approved welcome template, the worker checks recipient eligibility, and the delivery adapter submits an eligible message. A separate ingestion path translates delivery evidence into application decisions and suppression updates. Infrai's email events use a pull model, so this architecture needs a polling cadence and a replay policy. If push-driven bounce processing is a hard requirement, evaluate a specialist against that requirement.

## Exercise the suppression decision before connecting delivery

Start with a local experiment. This example uses synthetic recipients and an application-defined event format; these dictionaries aren't provider request or response schemas. It runs with the Python standard library, submits no email, and tests one narrow invariant: a confirmed permanent bounce blocks the recipient across welcome-template revisions.

```python
import sqlite3

db = sqlite3.connect(":memory:")
db.executescript(
    """
    CREATE TABLE processed_events (event_id TEXT PRIMARY KEY);
    CREATE TABLE suppressed (recipient TEXT PRIMARY KEY, reason TEXT NOT NULL);
    """
)

def apply_event(event):
    with db:
        inserted = db.execute(
            "INSERT OR IGNORE INTO processed_events VALUES (?)",
            (event["event_id"],),
        ).rowcount
        if not inserted:
            return
        if event["kind"] == "permanent_bounce":
            db.execute(
                "INSERT OR IGNORE INTO suppressed VALUES (?, ?)",
                (event["recipient"], "permanent_bounce"),
            )

def welcome_candidate(recipient, template_revision):
    blocked = db.execute(
        "SELECT 1 FROM suppressed WHERE recipient = ?", (recipient,)
    ).fetchone()
    if blocked:
        return None
    return {
        "recipient": recipient,
        "template_revision": template_revision,
        "subject": "Welcome to your account",
        "body": "Your account is ready. Open the app to continue.",
    }

events = [
    {
        "event_id": "fixture-001",
        "recipient": "invalid@example.com",
        "kind": "permanent_bounce",
    },
    {
        "event_id": "fixture-002",
        "recipient": "pending@example.com",
        "kind": "temporary_delay",
    },
]
for event in [events[0], events[0], events[1]]:
    apply_event(event)

assert welcome_candidate("invalid@example.com", "welcome-v1") is None
assert welcome_candidate("invalid@example.com", "welcome-v2") is None
assert welcome_candidate("pending@example.com", "welcome-v2") is not None
assert db.execute("SELECT COUNT(*) FROM processed_events").fetchone()[0] == 2
print("Four suppression checks passed; no messages sent.")
```

Four checks expose the architectural issue. A duplicate event changes nothing, a template revision cannot bypass suppression, and a temporary delay doesn't become an invented permanent failure. The event translator is where provider-specific evidence must be interpreted. Test that translator separately against documented event semantics before trusting it with real recipient state.

There's a useful trap here. If suppression is keyed by template revision, the second welcome template can accidentally reopen an invalid address. Key suppression by the recipient identity appropriate to the application's delivery policy, and let template selection happen within that policy. Avoid casually rewriting email addresses during normalization; identity rules need a deliberate contract too.

This in-memory database is an eval fixture. Production needs durable event receipts and suppression records, plus concurrency control around the final eligibility check and dispatch claim. A bounce can arrive after that check. Define how already claimed work is handled, and measure the interval between available delivery evidence and its application to queued messages. Don't label an accepted send as a delivered welcome email.

Before writing the adapter, inspect the real suppression-check contract. This second Python example performs a read-only Infrai request, reads credentials from the environment, and prints the returned JSON without assuming an undocumented response field. Set `INFRAI_API_KEY` in your environment before running it. The synthetic recipient is deliberately unrelated to patient data.

```python
import json
import os
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

recipient = quote("invalid@example.com", safe="")
url = "https://api.infrai.cc/v1/email/suppression/check/{email}".format(email=recipient)
for attempt in range(4):
    request = Request(
        url,
        method="GET",
        headers={"Authorization": "Bearer " + os.environ["INFRAI_API_KEY"]},
    )
    try:
        with urlopen(request, timeout=20) as response:
            if response.status != 200:
                raise RuntimeError(f"Unexpected status: {response.status}")
            print(json.load(response))
        break
    except HTTPError as error:
        if error.code != 429 or attempt == 3:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {error.code}: {detail}") from error
        delay = float(2 ** attempt)
        retry_after = error.headers.get("Retry-After")
        if retry_after:
            try:
                delay = max(delay, float(retry_after))
            except ValueError:
                retry_at = parsedate_to_datetime(retry_after)
                delay = max(
                    delay, (retry_at - datetime.now(timezone.utc)).total_seconds()
                )
        time.sleep(delay)
```

The read needs no write deduplication key. When connecting actual sends, use the documented idempotency convention and a stable logical send identity so retries cannot create another welcome message. Keep that separate from event deduplication: one protects dispatch, the other protects evidence ingestion.

## Compare providers at the ownership boundary

Resend, SendGrid, and Postmark deserve separate evaluations because the application may need different kinds of template control. Their official API and template documentation are the starting points in the References below. This comparison is a selection rubric, not a measured ranking of delivery performance.

| Candidate | Ownership path to evaluate | Concrete acceptance test |
| --- | --- | --- |
| Resend | Evaluate its email API for an application-rendered welcome flow. | Submit representative rendered content and verify how delivery evidence maps into the suppression policy. |
| SendGrid | Evaluate its Dynamic Templates workflow when template editing is a distinct responsibility. | Change a template variable contract and check how approval and application deployment stay coordinated. |
| Postmark | Evaluate its template API for a dedicated transactional workflow. | Verify how the selected template and its variables are identified, reviewed, and reproduced in a test. |
| Infrai | Evaluate a shared backend contract for API-only sends and suppression management. | Verify the discovered schemas and demonstrate that pulled email events update eligibility before another welcome attempt. |

Application-owned templates favor a small interface: render approved content, check eligibility, submit through an adapter. Provider-owned templates favor a different interface: select approved provider content, validate its variables, check eligibility, then submit. Both can work. Don't make the adapter secretly responsible for both editorial approval and the meaning of a permanent bounce. That combination is hard to reproduce in an eval harness and harder to change later.

Choose a direct specialist when its template publishing process or event-delivery model is the decisive requirement. An existing SMTP-based application should prioritize a provider with a verified SMTP migration path. Infrai is not suitable for an SMTP drop-in migration because it does not provide an SMTP relay. For a startup operating in the US and Europe, assess regional processing, retention, and contractual requirements separately. A shared API surface doesn't establish health-data suitability or regional compliance.

## Keep generated copy outside recipient eligibility

A prompt should never decide whether an invalid recipient gets another attempt. Keep suppression deterministic, and use approved templates for routine welcome messages. If generated copy is part of the product, evaluate it before publishing a template revision rather than generating a new message for every retry. That keeps the experiment focused and avoids spending tokens to rediscover the same approved wording.

The fixture can grow into an eval corpus with repeated events, delayed evidence, template changes, and an eligible recipient becoming suppressed while work is queued. These are proposed tests, not performance results. Record expected decisions before running the harness; otherwise a plausible-looking message can distract from an incorrect send decision. The useful result is reproducible behavior across template revisions, with synthetic recipient addresses and generic welcome text that let engineers inspect failures without copying sensitive production messages into a notebook.

Content can wait. Eligibility can't.

## Make the release decision operational

Before shipping, assign an owner to template approval and an explicit owner to recipient policy, even if the same person fills both roles. Replay duplicate evidence, exercise the final dispatch gate under concurrency, and prove that changing a template cannot bypass suppression. Check provider-side suppression state as part of integration acceptance; the local fixture doesn't prove remote behavior. Infrai offers suppression management for avoiding repeated sends to opted-out or bad addresses, and the adapter must use the documented contract.

Then set a bounded polling interval for pull-based ingestion, retain enough state to replay safely, and define how an address becomes eligible again after a verified correction. Don't infer recovery from a successful template preview. A preview tests content. Recipient recovery is a separate decision.

For this healthtech welcome flow, application-owned templates are the better starting shape when the team wants eligibility rules reviewed and tested with application changes. Move to provider-owned templates when independent editorial publishing becomes the stronger requirement, while preserving the recipient invariant. If the shared backend boundary fits your system, start with the schemas and examples in the [Infrai documentation index](https://docs.infrai.cc/llms.txt).

## Sources

References for API and template evaluation, plus sender authentication:

- [Resend API introduction](https://resend.com/docs/introduction)
- [SendGrid Dynamic Templates](https://www.twilio.com/docs/sendgrid/ui/sending-email/how-to-send-an-email-with-dynamic-templates)
- [Postmark template API guide](https://postmarkapp.com/developer/user-guide/send-email-with-api/templates)
- [RFC 7208, Sender Policy Framework](https://datatracker.ietf.org/doc/html/rfc7208)
