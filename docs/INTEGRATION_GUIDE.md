# Google Sheets, Google Drive, and Zapier

The finance service accepts PDFs, JPEGs, PNGs and WebP files at `POST /api/v1/documents`. The multipart fields are `file`, `project_id` (an existing project ID, not its display name) and optional `auto_record=true`. Authenticate with `Authorization: Bearer <REVIEWER_TOKEN>`. Get project IDs from authenticated `GET /api/v1/projects`.

Google and Zapier run outside your computer. Deploy the finance server at a reachable HTTPS URL with a valid certificate. `localhost` and private LAN addresses do not work. Keep your API token in Script Properties or private Zap configuration; do not put it in a spreadsheet or shared source. The token grants reviewer access, so restrict script editors.

## Google Sheets

1. Create a spreadsheet with a tab named **Expenses**. Set row 1 to `ID | Project | Category | Vendor | Date | Description | Amount | Currency`.
2. Open Extensions > Apps Script and paste `scripts/google_apps_script/SheetsWebhook.gs`.
3. Under Project Settings > Script Properties set `SPREADSHEET_ID` and `SHEETS_WEBHOOK_SECRET` (a new random secret of at least 24 characters).
4. Deploy as a Web App, execute as yourself, with access **Anyone**. Your Workspace administrator may restrict this setting. The script authenticates each request using its secret.
5. Configure the finance server and restart it:

```ini
SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/YOUR_DEPLOYMENT/exec
SHEETS_WEBHOOK_SECRET=YOUR_RANDOM_SECRET_AT_LEAST_24_CHARACTERS
```

The receiver locks concurrent writes, finds an existing expense ID and updates that row; retries do not append duplicates. It escapes formula-like document text and writes amounts as numbers. Keep the ID column intact. Only this database should write expenses into this tab. Recording is independent of delivery: a Google error leaves the expense recorded and its delivery failed. Retry with authenticated `POST /api/v1/expenses/{expense_id}/sync` (three attempts maximum).

The backend accepts only a JSON acknowledgement with `status: "ok"` and the matching expense ID. A sign-in page or HTTP 200 error response is a failed delivery. Google ContentService redirects to a one-time `script.googleusercontent.com` URL; the backend retrieves that response without resending the secret. See [Google ContentService](https://developers.google.com/apps-script/guides/content).

Alternative: set `SHEETS_SPREADSHEET_ID` and `SHEETS_ACCESS_TOKEN` and leave `SHEETS_WEBHOOK_URL` blank. Enable Sheets API, authorize a token with spreadsheet write access, and share the sheet with that identity. Tokens expire; this application does not refresh OAuth tokens. REST uses RAW input and reserved row numbers in `Expenses`; do not sort, delete or insert rows in that mode. Use a separate reporting tab for sorted views.

## Google Drive folder ingestion

Use a separate Apps Script project and paste `scripts/google_apps_script/DriveIngestion.gs`. In Script Properties configure:

| Property | Value |
| --- | --- |
| `API_BASE_URL` | Public HTTPS finance base URL, without `/api/v1` |
| `REVIEWER_TOKEN` | Same reviewer token as the finance server |
| `FOLDER_ID` | ID from your Drive folder URL |
| `PROJECT_ID` | Existing finance project ID |
| `AUTO_RECORD` | `true` to automatically record valid documents; otherwise `false` |
| `MAX_FILE_BYTES` | Optional; defaults to 10485760 and must not exceed server limit |

Run `processNewInvoices` once and authorize Google access. Then run `installDriveTrigger` once to schedule polling every five minutes. Upload a sample invoice into the folder and inspect Apps Script Executions plus the finance review queue. The authorized script account must be able to read the folder. The poller scans direct files, not nested folders; Google-native Docs/Sheets are excluded. Use one script per folder/project mapping.

The script sends each blob as multipart data and assigns a stable idempotency key to the project, Drive file ID and modification timestamp. It saves the returned document ID in Script Properties and polls its state. HTTP success alone is never counted as a recorded invoice:

- `RECORDED` and `DISMISSED`: stop polling that file version.
- `READY_TO_RECORD` and `NEEDS_REVIEW`: inspect and confirm in the finance UI; the script does not bypass review.
- `FAILED`: call the existing re-extraction endpoint, up to three attempts. Re-extraction follows the server's `AUTO_RECORD` setting, so set that server setting consistently with the script if you want retries to record automatically.
- Network/HTTP errors: keep the same idempotency key and back off. After five consecutive errors, pause the item. To resume after fixing configuration, edit its `drive-...` Script Property JSON: remove `paused`, reset `errors` and `retries` to zero, and remove `nextAttempt`; retain `documentId`. Do not erase state after an ambiguous timeout.

No files are renamed, moved or deleted. Files remain traceable in Drive. Duplicate file copies are also checked by the server. Changing a file creates a new version key. This lightweight poller uses persistent Script Properties and a continuation cursor; it handles at most two uploads/status checks per run and stops starting work after three minutes. One long request may still hit Google's execution limit. Apps Script is quota-limited, not unlimited: review [current quotas](https://developers.google.com/apps-script/guides/services/quotas), including execution time, URL Fetch and property storage. Archive completed state only after removing the corresponding source files from the watched folder; otherwise they will be considered again. For large volumes use a durable queue/Drive API worker.

Google references: [multipart URL Fetch](https://developers.google.com/apps-script/reference/url-fetch/url-fetch-app), [File.getBlob](https://developers.google.com/apps-script/reference/drive/file), [time triggers](https://developers.google.com/apps-script/reference/script/clock-trigger-builder).

## Zapier: Drive to finance

Webhooks by Zapier is listed as a premium app; verify your account's current plan before enabling the Zap. Do not assume the free plan supports this production workflow. See [Zapier's app listing](https://zapier.com/apps/webhook/integrations).

1. Trigger: Google Drive > New File in Folder. Connect the account with folder access and select the folder.
2. Action: Webhooks by Zapier > **POST**. URL: `https://YOUR_FINANCE_HOST/api/v1/documents`. Payload Type: **form**.
3. Map the action's **File** field to the Drive step's actual file object/download output. This must become a binary multipart part named `file`. A Drive sharing/view URL is not file content. If the trigger only supplies metadata, add a Google Drive action that retrieves the file before this step. Do not make private financial documents publicly shared just to make a URL work.
4. In Data, add `project_id` with the existing finance project ID and `auto_record` with `true` or `false`. Add headers `Authorization: Bearer YOUR_REVIEWER_TOKEN` and `Idempotency-Key: zapier-<project ID>-<Drive file ID>-<modified timestamp>` (keep the resulting key below 200 characters). Leave Content-Type unset so Zapier creates the multipart boundary.
5. Test with an actual PDF. Confirm the request has the binary `file` part; a 422 response usually means a required form/file field is missing. Confirm response `document.id` and `document.state` in the finance UI before enabling the Zap.
6. Route `NEEDS_REVIEW`/`READY_TO_RECORD` to human review and `FAILED` to investigation; HTTP 200 does not mean recorded. Replaying the same upload key returns the same document. To retry a failed extraction use authenticated `POST /api/v1/documents/{id}/reextract`; do not create new keys to evade idempotency. Do not run both this Zap and the poller for the same folder unless you intentionally want duplicate submissions.

Use POST, not Custom Request: Zapier explicitly states that Custom Request cannot send file objects. Refer to [sending webhooks](https://help.zapier.com/hc/en-us/articles/8496326446989-Send-webhooks-in-Zaps) and [sending files](https://help.zapier.com/hc/en-us/articles/8496288813453-Send-files-in-Zap-workflows). Field names and availability can vary by connector version; the API requires an actual multipart upload, not JSON containing a URL. If your action cannot produce it, use the supplied Apps Script integration.

## Verification

Record one test expense, check its row in Expenses, then retry the same delivery and ensure no duplicate row appears. Upload a file into the watched folder and confirm its project and review/recorded status. Check finance Operations for delivery failures and Apps Script Executions/Zap History for ingestion failures. Automated tests use fake HTTP transports; they do not prove your Google account, deployment permissions or live credentials are connected.
