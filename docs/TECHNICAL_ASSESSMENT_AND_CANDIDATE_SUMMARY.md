# Technical assessment coverage and candidate summary

This note maps the supplied **AI Agents & Automation Developer** assessment to the two implementation repositories and separates verified prototype scope from remaining submission work. It is intended to help reviewers understand the work quickly; it is not a claim that every deliverable has already been submitted or production-deployed.

## Executive summary

The assessment's two agent tracks are implemented as **two independent Python/FastAPI applications**, not as one integrated application:

- **Financial Document Assistant:** this repository, with multimodal PDF/image intake, extraction and validation, reviewer workflow, expense reporting, currency conversion, and Google integrations.
- **Content Generation & Publishing Agent:** [AhmedMagdi2003/Content-Agent](https://github.com/AhmedMagdi2003/Content-Agent), with source-grounded channel drafts, revision history, explicit approval, and a local mock publisher.

The strongest differentiators are the safety boundaries around uncertain financial data and publication: questionable expenses are held for review, and content edits invalidate earlier approval. The current finance walkthrough demonstrates finance features only. The assessment asks for one demonstration of **both** agents and the approval-triggered publishing flow, so a combined, under-five-minute demo remains to be recorded. Publishing is demonstrated against a local test publisher, not Impact Circles' real website or social accounts.

## Requirement coverage

| Assessment requirement | Implementation and evidence | Status |
|---|---|---|
| Upload invoices/receipts as PDFs or images | Finance upload UI/API accepts PDF, PNG, JPEG, and WebP; inspection routes text, vision, and mixed-page PDFs. See `app/inspection.py`, `app/web.py`, and the finance tests/fixtures. | Implemented; live-provider accuracy still needs a reproducible demonstration. |
| Extract date, vendor, invoice number, description, amount, currency, and tax | Structured candidate schema and extraction workflow in `app/ai.py` and `app/schemas.py`; supports OpenAI `gpt-4o-mini` and configured alternative providers. | Implemented; model output is evidence-based but must be reviewed where uncertain. |
| Categorize expenses | Category selection/classification is part of finance processing and review. | Implemented. |
| Maintain an expense tracker | Finance dashboard, API/CSV, PostgreSQL persistence, and Google Sheets sync; Drive intake is supplied as Apps Script/automation configuration. See `docs/INTEGRATION_GUIDE.md`. | Implemented; live Google deployment depends on the reviewer's own credentials and deployment settings. |
| Validate missing/inconsistent fields and duplicates | Deterministic checks and review queue prevent records with blocking issues from silently entering confirmed totals. | Implemented. |
| Summaries by category and currency | Finance reports support USD/EUR/EGP reporting conversion; source amounts remain unchanged and the UI displays rate pairs, provider, and rate date. | Implemented. |
| Accept a research update/event brief | Content Agent accepts a source brief through its dashboard/API. | Implemented in the separate Content-Agent repository. |
| Generate LinkedIn, newsletter, and website versions | Separate channel-specific generation and saved content records in `Content-Agent/app`. | Implemented; model-backed generation requires configured provider credentials. |
| Adapt content to each channel | Channel-specific drafting and presentation paths are implemented in the Content Agent. | Implemented. |
| Central content store/status | Content Agent persists content, revisions, approval decisions, operations, and publication status in its database. | Implemented. |
| Human review/edit/approve/reject/channel selection | Reviewer UI/API supports edits, rejection reasons, selected channels, and explicit approval. A new revision or changed selection invalidates prior approval. | Implemented; covered by automated tests and sample evidence in the Content-Agent repository. |
| Publish only after approval | Publishing checks the approved revision/digest and sends HMAC-signed, idempotent requests to a separate local test publisher. The assessment explicitly permits a local CMS/mock API when live sandbox accounts are unavailable. | Prototype flow implemented; production CMS/social API adapters and credentials are not claimed. |
| Record result, URL, timestamp, and notify of outcome | Per-channel publication state and returned local test URLs are recorded; the dashboard/API reports outcomes. | Implemented for the local mock publisher. |
| Working prototype, source, sample outputs, and technical docs | Two runnable repositories, test suites, sample output JSON/CSV, setup guides, and architecture/integration documentation. | Present across both repositories; see remaining actions below. |
| Demo, at most five minutes, showing both agents and post-approval publishing | Existing final finance video is a narrated, captioned finance walkthrough. It does not show the Content Agent or its approve-and-publish outcome. | **Not yet satisfied**; record a combined demo of both apps and the local publisher. |

## What was added beyond the assessment

- Finance reporting currency selection at the top of the app (USD, EUR, EGP), with converted summaries and individual expense views while preserving source amounts.
- Transparent exchange-rate pair/provider/date details using a free, keyless rate feed, with the clear limitation that these are reporting rates—not settlement/accounting rates.
- Batch ingestion, Google Drive polling/idempotency, Sheets update/delete reconciliation, operational traces, bounded model-cost controls, and multi-user action attribution.
- Content follow-up context and block-level citations in the separate Content Agent, in addition to the requested three-channel drafting and publishing workflow.
- A local test CMS/social publisher so the approval-to-publication path can be exercised without using real organizational accounts.
- English narration and English/Arabic captions for the existing finance walkthrough.

These additions are prototype capabilities; external service setup and live-account verification remain environment-dependent.

## Candidate positioning

> I built two practical AI-agent prototypes for Impact Circles: a finance workflow that turns PDFs and image invoices into validated, reviewable expense records, and a content workflow that turns research updates into channel-specific drafts with source evidence. I focused on the hard operational parts—not just prompting—including deterministic validation, duplicate and uncertainty handling, human approval, revision integrity, idempotent integrations, auditability, and cost-aware execution. The finance agent supports multi-currency reporting and Google Sheets/Drive workflows; the content agent demonstrates approval-gated publication through a local test publisher. I can walk through the architecture, tests, trade-offs, and what would be required to connect production accounts.

### Resume / application bullets

- Built a multimodal financial-document processing service for PDF and image invoices, combining LLM extraction with schema validation, duplicate checks, arithmetic controls, and a human review queue.
- Implemented expense tracking and Google integrations, plus unified USD/EUR/EGP reporting with visible exchange-rate provenance while preserving original transaction amounts.
- Developed a research-content agent producing LinkedIn, newsletter, and website drafts with persisted revisions, source citations, approval invalidation, and a strict human publication gate.
- Added signed, idempotent publication to a local sandbox publisher and operational records for publication outcomes; documented the boundary between prototype and production platform integrations.

## Honest submission checklist

1. **Record a combined demo under five minutes.** Show a finance invoice/image workflow, one validation/review decision, the currency selector/rate details, then a content brief, all three drafts, an edit, approval, and the resulting local test publication URL/status.
2. **Both offline suites and linters now pass in this workspace:** Finance `74 passed`; Content Agent `29 passed`; `ruff check .` passes in both repositories. These are local offline checks, not live provider or Google-account tests.
3. **Verify live integrations only with test accounts.** Automated tests and local mock results do not prove the user's Google deployment, API credentials, real CMS, or social accounts are connected.
4. **Submit both repository links** because the two agents are maintained separately. Include the demo and sample outputs, and do not upload `.env`, credentials, private documents, or raw recordings.

The positioning above is designed to make the work easy to evaluate without overstating live deployment or model accuracy. It cannot guarantee a hiring outcome.
