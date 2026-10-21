# Verified operator walkthrough (target 4:45)

No video was recorded. This script uses observed application behavior, not simulated
screens. It demonstrates an offline fixture workflow and real HTTP test publishing;
it does not demonstrate live AI extraction or cloud persistence.

## Preparation

Follow README's offline quickstart. Start both local servers on 8000 and 8011.
Sign in using the locally configured reviewer token. Keep `.env` off screen.
Use a fresh demo for a clean review case, or use existing confirmed documents and
the duplicate currently awaiting review. For a new empty demo, stop both servers,
move `.env` and `data/` to a private backup, then rerun `scripts.demo_setup`.
This is an operator reset; no cloud data should ever be deleted.

`uv run python -m scripts.smoke_demo` creates/updates actual sample output exports.
It expects only its own fixture records and checks EUR 240 / USD 45.50. Re-running
reuses confirmed files, adds a fresh content item, and skips no approval gate.

## Recording sequence

| Time | Action | Observable evidence |
|---|---|---|
| 0:00–0:20 | Open Financial Operations | Two modules and the explicit demo/fixture banner |
| 0:20–1:00 | Select River Research; upload `tests/fixtures/digital.pdf` | Original preview, candidate fields, status READY TO RECORD (or existing recorded document if already uploaded) |
| 1:00–1:45 | On a fresh demo upload `missing-total.pdf`; attempt Confirm; set grand total 120.00; Edit & revalidate; Confirm with original-based justification if review issues remain | Missing-total blocker refuses confirmation; amendments and corrected record are retained |
| 1:45–2:10 | Return to tracker; show EUR/USD separately; export CSV | Confirmed-only tracker and currency-safe summary; optional Sheets shows pending/not configured |
| 2:10–2:55 | Content Operations; paste `tests/fixtures/project-update.txt`; generate | Three distinct **demo template** drafts; no publishing yet |
| 2:55–3:30 | Edit website draft; save revision; select channels if needed and save again | New revision, awaiting approval; changed channel set bound to revision |
| 3:30–4:10 | Click Approve & Publish; open website and LinkedIn test links | Actual HTTP requests, published statuses, UTC timestamps, local test pages |
| 4:10–4:30 | Show Operations and search document/content ID | Safe routing/review/publish events and timings; no model usage claimed in fixture mode |
| 4:30–4:45 | Mention reproduction commands and outstanding cloud verification | Honest limits; both required workflows visibly demonstrated |

The UI save/edit/approve sequence was exercised in the browser on 21 October 2026:
content ID `75c1dc2e-a64c-4fa0-82cf-69e3d9dacb36`, revision 2, all three destinations
published on their first attempt. See `docs/screenshots/publication-2026-10-21.png`.
This URL is local and requires the retained demo database, not a hosted submission URL.
The separate automated real-HTTP run's IDs/URLs are in `sample_outputs/smoke-evidence.json`.
Rejection was also verified in the browser on content
`d02e0dde-25e2-4936-8e9e-ba5075656934`: the reason is retained and publication is
blocked until a revised draft is saved. This is optional footage if time permits.

Keep browser text readable. Include titles/outro in the <=300-second measurement.
Record to a private path under `recordings/` (ignored), verify playback and duration,
and publish/share only after reviewing the recording for secrets. No recording
facility was established during this run; screenshots and this script are provided.
