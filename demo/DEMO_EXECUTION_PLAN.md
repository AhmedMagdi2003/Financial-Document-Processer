# Demo Execution Plan

Target duration: 60–90 seconds. The current deliverable is a currency-reporting preview using a separate local demo database with three fictional expenses. It demonstrates the new reporting feature; it is not evidence of the separate AI extraction or Drive/Sheets workflows.

| Scene | Input / action | Expected result | Evidence to capture | Time |
|---|---|---|---|---|
| Introduction | Open the isolated local demo | Financial Operations page; sample data are clearly fictional | English narration and fictional-data badge | 8s |
| USD report | Show starting report | Converted aggregate and selected currency visible | Global top-bar selector, total and rate date | 12s |
| EGP conversion | Change the top-bar selector to EGP | Aggregate and each expense's converted display update | Selected EGP, total and source values | 10s |
| Rate details | Scroll to exchange-rate details | Provider timestamp, EUR/EGP and USD/EGP pairs, and source totals are visible | Exchange panel and converted source totals | 18s |
| Unified categories and timeline | Show combined tables/charts | Entries from USD, EUR and EGP are grouped in the selected reporting currency | Category and month totals | 10s |
| Close | Return to dashboard overview | Reporting currency and original amounts coexist | English sign-off on final dashboard overview | 26s |

## Preconditions

- Use a separate local SQLite database. Do not connect this preview to production Drive, Sheets, Supabase, or invoice uploads.
- The three entries are seeded synthetic values, not the result of an AI extraction run.
- Confirm the local server is reachable and use only the local demo reviewer token.
- Read `docs/FINANCIAL_DEMO_VIDEO_GUIDE.md` and preserve the raw recording.

## Verification rules

- Do not claim image/PDF extraction, review resolution, Drive, or Sheets success from this currency-only video.
- If those workflows are later added to a full product walkthrough, verify them in that same run and separately update `DEMO_EVIDENCE.md`.
- Read currency pairs and update timestamps from the running UI. Never use a hard-coded rate in overlays or narration.
