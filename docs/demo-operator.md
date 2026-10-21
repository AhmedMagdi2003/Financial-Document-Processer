# Finance segment: verified operator instructions

The Financial Document Assistant now runs alone on port 8000. Content generation,
approval and test publishing are in `content-agent/`; its demonstration instructions
are maintained there. No video has been recorded. The joint assessment video must
remain <=300 seconds; allocate approximately two minutes to finance.

Start finance using the root README, sign in with the root reviewer token, and keep
configuration files off screen. Upload a fictional PDF/image, compare its source
and fields, show a validation concern, edit/revalidate and confirm. Show confirmed
totals separately by currency, tracker CSV and pending/unconfigured Sheets state.
The demo provider is fixture replay, not live AI.

Use `tests/fixtures/digital.pdf`, `receipt.png` and `missing-total.pdf`. Repeated
uploads reuse existing records; the preserved demo includes confirmed examples and
a business duplicate awaiting review. For an empty demo, use a separate copy with
a new configuration/database; never delete existing cloud or local history as reset.

`uv run python -m scripts.smoke_demo` verifies the finance flow alone on 8000 and
exports its actual tracker/summary. It expects its own stable fixture totals, EUR
240.00 and USD 45.50. The source images and original content data remain preserved.
