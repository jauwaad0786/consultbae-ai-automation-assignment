# Task 5 — Scaling to 5,000 Workers in a Weekend

**One-pager, no code.** This looks at what happens if the audio app from Task 3 —
as built — was pointed at 5,000 gig workers submitting recordings over a single
weekend, and what we'd change before letting that happen.

## What breaks first

**1. The database connection.**
`backend.py` opens a brand-new MySQL connection for every single read/write
(`get_conn()` on every call) and there's only one local MySQL instance behind it.
A handful of people testing it locally is fine. A few hundred workers hitting
"Submit" in the same few minutes is not — MySQL's default `max_connections` gets
exhausted, and everyone after that just sees a connection error, not a friendly
"try again" message.

**2. Audio files filling up local disk.**
Every recording is saved straight to `/audio_storage/` on whatever machine is
running the app. At 5,000 submissions — even a modest 30-second clip each — that's
easily tens of GB landing on one disk. Once it fills up, every new submission
fails silently at the save step. And if the app restarts or gets redeployed, the
whole folder (and every audio file in it) is gone.

**3. Audio processing happening inside the request.**
Right now `process_submission()` saves the file, then immediately runs `pydub`
property extraction (duration, sample rate, bitrate, loudness) in the same request
— the worker's browser just sits there waiting the whole time. On a slow phone
connection with a larger file, that request can easily time out before extraction
even finishes, and the person has no idea if their submission actually went
through.

**4. Duplicate submissions from retries.**
Gig workers on patchy mobile networks will hit "Submit," see nothing happen after
a timeout, and hit it again. There's currently nothing stopping the same recording
from being saved and inserted into `submissions` two or three times over.

**5. No visibility when things go wrong.**
If uploads start failing at 2am on a Saturday, nobody finds out until someone
manually checks — there's no logging or alerting on failed saves, failed DB
writes, or a growing backlog.

## What we'd change before launch

- **Move off a single local MySQL instance** to a managed database (RDS / Cloud
  SQL) with a proper connection pool in front of it, so thousands of short-lived
  requests don't each pay the cost of opening a fresh connection — and so the app
  doesn't fall over the moment concurrent traffic shows up.
- **Move audio storage off local disk to object storage** (S3 / Cloudflare R2).
  It doesn't fill up, it survives a redeploy, and it scales without anyone
  babysitting disk space.
- **Take audio processing out of the request path.** Save the raw file fast,
  return "submission received" to the worker immediately, and run the actual
  `pydub` extraction in a background job (a simple queue like Celery/RQ is
  enough). The worker isn't stuck waiting on their phone for a calculation they
  don't need to see happen live.
- **Add an idempotency key** — something like a hash of phone number + a
  client-generated submission ID — so a retried upload updates the existing
  attempt instead of creating a new row every time.
- **Add basic rate limiting per phone number** and **validate file size/format on
  the client before upload starts**, so a bad or oversized file doesn't waste
  bandwidth and server time before failing anyway.
- **Add monitoring from day one** — failed upload count, queue backlog size, disk/
  storage usage — with an alert if any of those start climbing, instead of finding
  out from angry workers on Monday.
- **Put a rough cost estimate and a budget alert in place** for storage and audio
  processing compute before the weekend starts, not after the bill arrives —
  5,000 files processed and stored is a small but real cost that's worth knowing
  upfront rather than discovering later.
