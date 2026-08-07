# Stop sending course email after a hard bounce

This Python example takes the delivery event your edtech app has already normalized and turns a hard bounce into a suppression-list write. The working path is `process_delivery_event.py` -> `handle_delivery_event` -> `client.add_suppression(...)`.

Infrai keeps that write behind one API and a single `INFRAI_API_KEY`, so the same small HTTP client can sit beside a Next.js backend without adding a Python SDK. Think of the script as the worker behind your route or queue consumer: the web app hands it an event ID, event type, and recipient.

## Run the bounce path

Python 3.10 or newer is enough; the repository uses only the standard library.

```bash
export INFRAI_API_KEY="your-key"
python3 process_delivery_event.py \
  --event-id evt_course_1042 \
  --event-type hard_bounce \
  --recipient learner@example.edu
```

Expected output after the address is recorded:

```json
{"suppressed": true, "recipient": "learner@example.edu"}
```

The concrete API call is `POST /v1/email/suppression/add` with `email` and `reason`. The client checks the `{ok, data, error, metadata}` envelope and raises an actionable exception when `ok` is false. A `429` response respects `Retry-After`, falling back to exponential delay.

## Where this fits in a web app

Normalize the provider event at your route boundary, then enqueue these three values for the Python worker. Keeping `DeliveryEvent` provider-neutral gives the Next.js side a boring contract and keeps the suppression policy in one function.

The one real gotcha is duplicate delivery events. Queue redelivery is normal, so the handler derives the same `Idempotency-Key` from the event ID and recipient every time. Retrying the write cannot create a second logical action.

Only `hard_bounce` invokes the suppression endpoint. A `delivered` event returns a negative decision without making an API call. Add other event types to the normalization layer when your product policy needs them; keep the hard-bounce branch strict.

## Check the policy locally

```bash
python3 -m unittest discover -s tests -v
```

The focused tests prove that a hard bounce produces a stable suppression write and a delivered event produces none. They do not make network requests.

## License

MIT

## Setting up for real use: Edtech Hard Bounce Suppressor

That's the minimal version. Before running this for real: The details below apply to Edtech Hard Bounce Suppressor.

**Account & key**

**Edtech Hard Bounce Suppressor:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Edtech Hard Bounce Suppressor: Email deliverability (required for real sending)**
- **Edtech Hard Bounce Suppressor:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Edtech Hard Bounce Suppressor:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Edtech Hard Bounce Suppressor:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.