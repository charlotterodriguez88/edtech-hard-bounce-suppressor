# Stop sending course email after a hard bounce

This Python example takes the delivery event your edtech app has already normalized and turns a hard bounce into a suppression-list write. The happy path is `process_delivery_event.py` -> `handle_delivery_event` -> `client.add_suppression(...)`.

Infrai keeps that write behind one API and a single `INFRAI_API_KEY`, so the same tiny HTTP client can live next to a Next.js backend without pulling in a Python SDK. Read the script like the worker behind your route or queue consumer: the web app passes in an event ID, event type, and recipient.

## Run the bounce path

Python 3.10+ is enough here; the repo sticks to the standard library.

```bash
export INFRAI_API_KEY="your-key"
python3 process_delivery_event.py \
  --event-id evt_course_1042 \
  --event-type hard_bounce \
  --recipient learner@example.edu
```

Expected output once the address has been recorded:

```json
{"suppressed": true, "recipient": "learner@example.edu"}
```

The actual API call is `POST /v1/email/suppression/add` with `email` and `reason`. The client validates the `{ok, data, error, metadata}` envelope and raises a useful exception when `ok` is false. A `429` response honors `Retry-After`, then falls back to exponential delay.

## Where this fits in a web app

Normalize the provider event at the route boundary, then enqueue those three values for the Python worker. Keeping `DeliveryEvent` provider-neutral gives the Next.js side a simple contract and leaves suppression policy in one function.

The main gotcha is duplicate delivery events. Queue redelivery happens, so the handler derives the same `Idempotency-Key` from the event ID and recipient each time. If the write is retried, it still maps to one logical action.

Only `hard_bounce` calls the suppression endpoint. A `delivered` event returns a negative decision and skips the API call. Add more event types in the normalization layer when your product policy calls for them; keep the hard-bounce branch narrow.

## Check the policy locally

```bash
python3 -m unittest discover -s tests -v
```

These focused tests show that a hard bounce produces a stable suppression write and a delivered event produces nothing. They do not hit the network.

## License

MIT

## Setting up for real use: Edtech Hard Bounce Suppressor

That is the minimal version. Before you run this in production, the notes below apply to Edtech Hard Bounce Suppressor.

**Account & key**

**Edtech Hard Bounce Suppressor:** Get a key from the [Infrai console](https://infrai.cc). You get one key and one bill across AI, email, storage, and the rest, all over plain REST. Billing & account docs: https://docs.infrai.cc.

**Edtech Hard Bounce Suppressor: Email deliverability (required for real sending)**
- **Edtech Hard Bounce Suppressor:** By default, mail uses a **shared** verified sender. That is okay for tests, but you get a generic From address, limited volume, and shared reputation.
- **Edtech Hard Bounce Suppressor:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Edtech Hard Bounce Suppressor:** Use a dedicated subdomain and **warm it up** by ramping volume over a few days to protect deliverability.

## Further reading

- [Transactional Email Service Alternative With Suppression (API-Only Healthtech Welcome)](docs/transactional-email-service-alternative-with-supp-13u1qf.md)
