# Financial Document Assistant demo video guide

This guide is for recording a short, truthful product walkthrough of the Financial Document Assistant. Keep the final cut between 60 and 90 seconds and retain the unedited Playwright capture in `demo/raw_recordings/`.

The spoken narration must be in English. The demo voiceover script uses an English (US) neural voice; the optional voice-rendering step sends only that narration text to Microsoft's online speech service, never expense or invoice data.

## Story and on-screen proof

1. **Open with the product (0:00–0:08).** Show the real application, not a mock-up.
2. **Show intake and extraction (0:08–0:28).** Use fictional sample documents only. Include an image receipt or scanned invoice and the multi-page PDF flow if those cases are part of the run. Show the actual document status and extracted fields.
3. **Show the safety gate (0:28–0:43).** Use a genuine review case, such as a missing-currency sample. Show the issue and `NEEDS_REVIEW`; do not imply it was recorded before reviewer action.
4. **Show the expense dashboard (0:43–0:55).** Show confirmed records and any integration status. Only show Drive/Sheets as successful when that same run has visible external and application-side evidence.
5. **Show unified currency reporting (0:55–1:15).** Change the global top-bar reporting currency (USD, EUR, or EGP). Capture the aggregate, charts/tables, and per-expense converted display updating together. Keep source amounts and the source-currency breakdown visible where possible. Show the live exchange-rate pair(s), provider, and update timestamp/date.
6. **Close (1:15–1:20).** Briefly show operational traceability and the human-review safeguard.

## Currency accuracy

- Read rates and dates from the running application during recording. Never insert a remembered, manually typed, or static rate as if it were live.
- State that conversion is for reporting. Original invoice amounts and stored expense values remain unchanged.
- If the rate API is unavailable, preserve the original amounts and explicitly say the converted view could not be demonstrated; do not make up values.
- Distinguish the provider's rate publication date/time from the date of the underlying transaction.

## Recording and edit

- Use Playwright to drive the real application and record at 1440×900. Wait for visible states; do not replace processing screens with fabricated “success” overlays.
- Preserve the browser's original video file under `demo/raw_recordings/`; do not overwrite a prior capture. Save the edited deliverable as `demo/output/finance_agent_demo.mp4`.
- If a wait is shortened, add the on-screen caption: “Processing wait time shortened; original recording retained.” Do not remove a failure or review outcome that changes the meaning of the workflow.
- Use concise captions and readable text. Avoid exposing API tokens, private customer information, or real invoices; use fictional test inputs and a test workspace.
- Record the real run's scenario, outcome, verification source, video timecode, and rate/date in `demo/DEMO_EVIDENCE.md`. If any external service cannot be verified, label it unverified.

## Preflight and completion checklist

- Confirm the app and its test data source; do not point a demo upload at an unverified production destination.
- Confirm image and multi-page PDF processing with real app responses if shown.
- Confirm the selected reporting currency updates all converted views and the pair/date display.
- Confirm raw capture and final edit are both present, and the final duration is 60–90 seconds.
- Watch the exported MP4 from beginning to end and check audio, legibility, and that claims match the visible evidence.
- Only mark the video complete after export and playback inspection; list any unverified integration in the evidence log.
