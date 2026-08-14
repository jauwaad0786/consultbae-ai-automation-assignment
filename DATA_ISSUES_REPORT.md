# Data Issues Report — Task 4

**ConsultBae AI Automation Assignment**
Author: Jauwaad Bin Irshad

## Overview

We were given three CSV files from three different systems — naukri applicants, gig
workers, and CBNexus contacts — and asked to merge them into one clean database. None
of the files shared a common ID, and the data itself had a number of quality problems
baked in. This report lists every issue we found while building the merge pipeline
(Task 1), how many rows it affected, and exactly what we did about it.

**Record counts through the pipeline:**

| Stage | Naukri | Gig | CBNexus | Total |
|---|---|---|---|---|
| Raw records loaded | 42 | 32 | 31 | **105** |
| After removing junk/malformed rows | 42 | 30 | 30 | **102** |
| After removing duplicate rows | 40 | 30 | 30 | **100** |
| Final unique people after merge | — | — | — | **55** |

## Issues Found and How We Handled Them

| # | Issue | Rows Affected | What We Did |
|---|---|---|---|
| 1 | **Completely blank row** in the gig file — every column empty. | 1 row (gig) | Dropped it. There was nothing usable in the row at all. |
| 2 | **Column-shifted row** in the gig file — the values were sitting under the wrong headers (e.g. skill tags appeared in the email column, a name appeared in the rate column). | 1 row (gig) | Set it aside separately instead of guessing which value belonged where. Merging a row with scrambled columns risks writing wrong data into the master table, so we quarantined it for manual review rather than force-fitting it. |
| 3 | **A literal header row saved as data** in the CBNexus file — one row just repeated the column names ("Name", "Phone Number", "City"...) as if it were a person. | 1 row (cbnexus) | Detected and dropped it — it's clearly not a real contact. |
| 4 | **Duplicate people within the naukri file itself**, submitted more than once with the same phone number but a slightly different email (one copy had an "alt." prefix on the email) or a shortened name (e.g. "R. Verma" vs "Rohit Verma"). | 4 rows → 2 people (naukri) | Treated same phone number as the same person and kept one record per person, preferring the non-"alt." email as the primary one. |
| 5 | **Phone numbers written in five different formats** across the three files — plain 10-digit, with a leading 0, with a leading 91, with a "+91" prefix, and with a "+91-" hyphen. | All rows with a phone number (naukri, cbnexus) | Normalized every phone number down to its last 10 digits, stripping any country code, leading zero, spaces, or hyphens, so the same person's number always looks identical no matter which file it came from. |
| 6 | **City names spelled/cased inconsistently** — e.g. "GURGAON", "gurugram", "Gurugram" (with a trailing space) all referring to the same city; similarly for Noida, Delhi, Pune, and Bengaluru/Bangalore. | Most rows across all three files | Built a lookup table mapping every known spelling/casing variant to one standard city name, and trimmed stray leading/trailing spaces. |
| 7 | **Inconsistent status and verification values** — the gig file's "status" column had Active / active / ACTIVE / Inactive / paused all mixed together; the CBNexus "Verified" column had Y / N / Yes / No / yes in different cases. | ~30 rows (gig), ~30 rows (cbnexus) | Lower-cased the status field for consistency, and converted Verified into a clean true/false value (Y, Yes, yes → true; N, No → false). |
| 8 | **Applied dates written in at least four different formats** in the same column — e.g. "24-07-2026", "2026-08-08", "7 Jul 2026", and "07/13/2026" all appear side by side. | 42 rows (naukri) | Tried each known date format in order until one parsed successfully, so every date lands in one consistent format. |
| 9 | **CTC values mixed two different units in one column** — some rows had small numbers like 4.2 or 11.9 (meant as lakhs), others had large numbers like 417964 or 1195422 (plain rupees) — same column, no unit label. | 21 rows (naukri, out of 42) | Treated any value under 50 as being "in lakhs" and multiplied it by 100,000, so the whole column ends up in the same rupee unit. |
| 10 | **Gig worker rates mixed two different pay units** — some as "X/hr" (hourly) and some as "Xk/month" (monthly), in the same rate column with no separate unit field. | 16 hourly + 14 monthly rows (gig) | Converted every monthly rate to its hourly equivalent (dividing by an assumed 160 working hours/month) so all rates are comparable on one scale. |
| 11 | **Same name belonging to different people (false-match risk)** — CBNexus has "Arjun Mehta" appearing twice with two different phone numbers, and a separate, similarly-named "Arjun Mishra". Blindly matching on name alone would have merged two different individuals into one. | 3 rows (cbnexus) | Only merged people by name as a last-resort fallback, and only when the name AND city matched exactly with nothing else contradicting it. Phone/email always take priority over name, so these stayed as separate people. |
| 12 | **No single ID common to all three files** — naukri has both email and phone, gig has only email, cbnexus has only phone. There was no direct way to join all three on one key. | All 100 cleaned rows | Used naukri as the "bridge" source since it has both identifiers: matched gig records to it by email, and cbnexus records by phone. Anyone left unmatched after that was given one more chance to match via name + city between gig and cbnexus. Anyone still unmatched after all three passes was kept as their own standalone person, so no record was ever silently dropped. |

## Final Matching Result

Out of the 100 rows left after cleaning and dedup:

- **Gig → naukri match (by email):** 15 out of 30 rows matched directly.
- **CBNexus → naukri match (by phone):** 25 out of 30 rows matched directly.
- **Name + city fallback match:** 5 more gig/cbnexus rows matched to each other this way.
- Everyone else was kept as a standalone person rather than dropped or force-merged.

This brought the 100 cleaned rows down to **55 unique people** in the final master
table — meaning a fair number of people appeared in more than one source file, which
confirms the overlap between the three systems was real and not just noise.

## Judgment Calls

- We chose **not** to auto-merge people purely on name similarity, because of the
  Arjun Mehta / Arjun Mishra case above. A looser name-matching rule would have
  silently combined two different people into one record — which is a worse outcome
  than leaving them unmerged.
- The column-shifted row in the gig file was **quarantined, not repaired**. We could
  have tried to guess the correct column order, but that risks writing wrong data
  into a real person's record. Flagging it for manual review was the safer call.
