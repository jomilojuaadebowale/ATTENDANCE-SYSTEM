# Security and privacy

## What is protected, and how

| Concern | Control |
|---|---|
| Who are you? | Firebase ID tokens verified on the server (`AUTH_PROVIDER=firebase`). |
| What may you do? | `users.role` in our database; each endpoint requires a role; lecturers only reach courses they are assigned to; students only see their own data. |
| Fake dev login in production | Settings refuse to start with `AUTH_PROVIDER=dev` or wildcard CORS when `ENVIRONMENT=production`. |
| Forged QR codes | HMAC-SHA256 signature, constant-time compare, 20 s slots. |
| Replays / double counting | unique `client_uuid`; unique (session, student). |
| Proxy attendance | geofence, device binding, flags for lecturer review. |
| Silent edits | every manual mark, review, role change, device reset and cancel writes `audit_log`. |
| Brute force / floods | per-process rate limits on sync and auth endpoints. |
| SQL injection | SQLAlchemy parameterised queries only. |
| CSV formula injection | exported cells beginning with `= + - @` are prefixed with `'`. |
| Secrets in git | `.env`, keys and dumps are git-ignored; `.env.example` has placeholders only. |
| Browser storage | the app stores no tokens in localStorage (Firebase manages its session); localStorage holds only the random device id; dev mode keeps the email in sessionStorage. |
| Security headers | set in `next.config.ts` for the web app; API uses bearer tokens, no cookies. |
| Dependencies | `npm audit --omit=dev` reported 0 vulnerabilities at the time of the last run. |

## Known limits (be upfront about these)

1. **GPS can be spoofed** and QR codes can be relayed live by a friend inside the room. The system raises the effort
   and records evidence; it cannot prove physical presence.
2. **Offline scan time is self-reported** by the phone.
3. **Rate limiting is in memory**, per process. Multiple instances need a shared limiter.
4. **Firebase mode has not been exercised against a live Firebase project** in this repository's test runs; tests
   use the dev provider and the verification code path is a thin wrapper over `firebase-admin`. Test it with a real
   project before relying on it.
5. **Docker images were not built or run** in the authoring environment (no Docker daemon); `docker compose config`
   validates the file only.
6. The lecturer's device holds the session signing secret when using local QR generation.
7. No automated backups, monitoring or alerting are included.
8. Rejected scans are not stored, so there is no server-side record of failed attempts.
9. Token revocation is not checked (`check_revoked=False`) to avoid an extra network call; a disabled Firebase
   account remains valid until its token expires (about an hour). Deactivate the user in our DB for immediate
   effect (inactive users are refused).

## Privacy

**Data collected:** name, email, matric/staff number, role; enrolment; per-scan latitude/longitude/accuracy, device
id, device time, outcome; manual-mark reasons; audit entries.

**Principles in the design**

* Location is requested only at the moment of a scan, once, never tracked continuously.
* Location is used to decide a single scan and is kept on that attendance row as evidence for review.
* Students see only their own records; lecturers see only their own courses.
* The QR payload contains no personal data.

**What an institution still needs to decide** (not implemented here): lawful basis and notice to students (for
Nigeria, the NDPA 2023), a retention period for location data and a job to purge it, who may export reports, and a
process for access/correction requests. Consider rounding or deleting coordinates after the review window.

## Hardening checklist before real use

- [ ] HTTPS everywhere; correct `CORS_ORIGINS`.
- [ ] Real Firebase project, tested end to end; email verification enforced.
- [ ] Secrets in a secret manager; rotate any credential ever pasted into chat or a repo.
- [ ] Managed PostgreSQL, backups, least-privilege DB user.
- [ ] Shared rate limiter, log shipping, error monitoring.
- [ ] Retention policy for location data.
- [ ] Penetration test or at least a review by someone who did not write it.
