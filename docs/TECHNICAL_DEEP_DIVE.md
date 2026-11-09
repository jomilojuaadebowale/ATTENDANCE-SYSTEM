# Technical deep dive: QR, time, location, offline

This explains the parts that make the system "better than a plain QR scan". Everything here matches the code in
`apps/api/app/services/{qr_service,geo_service,attendance_service}.py` and `apps/web/lib/{qr,geo,offline-queue,scan-flow}.ts`.

## 1. The rotating QR

**Goal:** a photo of the projector screen sent to a friend an hour later must not work.

Payload: `v1.<session_id>.<slot>.<signature>`

* `slot = floor((now - starts_at) / slot_seconds)`; default `slot_seconds = 20`.
* `signature = base64url(HMAC-SHA256(secret, "<session_id>:<slot>"))`, first 22 characters.
* `secret` is random, per session, 256 bits, created by the server.

```text
sign(secret, session_id, slot):
    msg = session_id + ":" + slot
    return base64url(hmac_sha256(secret, msg))[0:22]

valid(scan):
    parts = scan.split(".")           # v1, id, slot, sig
    return constant_time_equal(parts.sig, sign(secret, parts.id, parts.slot))
```

Because the slot number is part of what is signed, nobody can change "slot 12" to "slot 13" without the secret, and
the server needs no per-slot storage: it recomputes the signature.

**Two ways the QR is produced**

1. `GET /sessions/{id}/qr` — the server signs and returns the current payload (needs the lecturer to be online).
2. `GET /sessions/{id}/qr-seed` — the lecturer's device downloads the secret **once** and signs locally with Web
   Crypto every slot. This keeps the projector QR rotating even if the lecturer's connection drops. Python and
   TypeScript are checked against shared test vectors so both produce identical signatures.

**Cost of option 2:** the secret is on the lecturer's device for the session. Only the session's owner (or an admin)
can fetch it, and it is never included in normal session responses.

## 2. Is the scan on time?

The student's phone sends `qr_slot` (from the QR) and `device_time` (its own clock). The server compares:

* **Online scan** (synced within `online_sync_window_seconds`, 120 s, of the scan): the *server's* clock is trusted.
  The slot must be within the tolerance (`clock_skew_tolerance_seconds`, 60 s) of "now".
* **Offline scan** (queued and synced later): the server cannot know when it happened, so it checks that
  `device_time` falls inside the slot's window ± tolerance. A phone with a wrong clock produces a `clock_skew` flag.
* **Late sync**: a sync arriving more than `sync_grace_minutes` (60) after the session ended is flagged `late_sync`.
* **Closed sessions**: an online scan after the session ended is rejected as `session_closed`.

**Honest limit:** an offline scan's `device_time` is self-reported. A student who changes the phone clock could replay
a QR they photographed during the session. The signature stops them inventing slots, and the geofence, device
binding and lecturer review reduce the benefit, but this is the price of allowing offline check-in. The grace window
and the flagging policy are the knobs that trade convenience for strictness.

## 3. Is the student in the room?

The browser's Geolocation API gives latitude, longitude and an **accuracy radius** in metres. The server computes the
Haversine (great-circle) distance to each anchor: the venue, and/or the point where the lecturer started the session.

```text
distance = haversine(student, anchor)
inside   = (distance - accuracy) <= radius      # accuracy gives the student benefit of the doubt
```

| Situation | Result |
|---|---|
| inside radius, accuracy ≤ 100 m | `verified` |
| no location sent | `flagged: no_location` |
| accuracy worse than 100 m | `flagged: low_accuracy` |
| outside radius with good accuracy | `rejected: outside_radius` (not stored) |
| impossible coordinates | `rejected` |

Default radius is 75 m (configurable per session, 5–1000 m). Indoor GPS is often 20–60 m off, which is why weak
fixes are flagged for a human instead of being rejected.

**Honest limits:** browser location can be faked with developer tools, a mock-location app or a VPN-style spoofer.
A relayed QR plus a faked location defeats the geofence. The system makes cheating inconvenient and auditable, not
impossible.

## 4. Offline-first

Flow on the student's phone (`lib/scan-flow.ts`):

1. Decode the QR; reject non-attendance codes immediately.
2. Request **one** location fix (a single request, not continuous tracking).
3. Generate a `client_uuid` and save `{payload, location, device_time, client_uuid}` to IndexedDB **before** any
   network call.
4. Try `POST /attendance/sync`. On success, remove from the queue and store the outcome.
5. On network failure, keep it queued. The UI says "saved on this phone, not yet confirmed" and never "present".
   Queued scans are retried when the browser comes back online or on a manual retry.

The server answers each scan with one outcome: `recorded`, `flagged`, `duplicate` or `rejected`, plus a code and a
message. Syncs of up to 100 scans are accepted per request.

## 5. Duplicates and races

* `client_uuid` is unique, so a retried request returns `duplicate` rather than a second row.
* `UNIQUE (session_id, student_id)` plus `INSERT ... ON CONFLICT DO NOTHING` makes two simultaneous scans safe.
  A concurrency test runs this against real PostgreSQL.

## 6. Device binding

The first successful scan binds the phone's `device_id` (random id stored in the browser) to the student. A different
device afterwards produces `flagged: device_mismatch`; a device already bound to another student gives
`shared_device`. A partial unique index guarantees one active device per student. An admin can reset a binding
(`POST /users/{id}/reset-device`) when a student gets a new phone. A cleared browser looks like a new device.

## 7. Manual marking and review

* Lecturers can mark a student present with a **required reason** (no phone, dead phone, network failure, app
  problem, other). The lecturer, reason and time are stored and an audit row is written.
* Lecturers may correct up to 24 h after the session ends; admins at any time.
* A flagged scan is reviewed with `POST /attendance/{id}/review` (`action`: `approve` → counts as verified; `reject` → not counted; a reason of 3+ characters is required).

## 8. Percentages

* Only **closed** sessions count; cancelled ones are ignored.
* Present = verified + manual. Flagged-and-unreviewed scans are pending and not counted.
* Eligibility threshold: 75 % (configurable).
* Excused absences (medical, etc.) are **not modelled**; an absent student stays absent in the numbers.

## 9. What is tested

The unit tests cover QR signing/parsing and Haversine; integration tests run against a real PostgreSQL database and
cover each outcome above, concurrency, corrections, reports and DB constraints. See the README for the latest counts.
