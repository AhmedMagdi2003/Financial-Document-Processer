# Integration Guide: Google Drive, Zapier & Google Sheets

This guide explains how organizations can automate financial document ingestion and spreadsheet synchronization with the **Financial Document Assistant**.

---

## 1. Automated Workflow Overview

```
[Invoice/Receipt Received]
        │
        ├─ Option A: User drops files in Web UI (Batch or Single)
        ├─ Option B: Dropped into Google Drive folder (Free Google Apps Script)
        └─ Option C: Zapier Trigger (Google Drive / Email / Slack)
        │
        ▼
[POST /api/v1/documents (auto_record=true)]
        │
        ▼
[Inspection & Routing] ─── Text-native PDF or Image/Scan Vision
        │
        ▼
[AI Extraction & Field Normalization]
        │
        ▼
[Multi-Layer Validation & Duplicate Check]
        │
        ├─────────────────────────────────────────────────┐
        ▼                                                 ▼
[ZERO Critical Conditions]               [ANY Critical Condition Occurs]
  • Valid total & currency                 1. Missing grand total
  • No duplicate detected                  2. Missing currency
  • Consistent arithmetic                  3. Potential duplicate
        │                                  4. Arithmetic conflict
        ▼                                                 │
[AUTOMATIC RECORDING]                                     ▼
  • Creates confirmed Expense              [DEDICATED REVIEW QUEUE]
  • Updates Document to RECORDED             • Tagged as NEEDS_REVIEW
  • Emits audit event                        • Human reviewer inspects original
        │                                    • Justified decision required
        ▼
[GOOGLE SHEETS SYNC]
  • Row upserted in spreadsheet
  • Real-time delivery status logged
```

---

## 2. Zapier Free-Plan Analysis & Honest Limitations

Before configuring Zapier, review these verified platform constraints:

| Feature | Zapier Free Tier | Zapier Starter / Pro |
| :--- | :--- | :--- |
| **Monthly Task Allowance** | 100 tasks / month | 750+ tasks / month |
| **Multi-step Zaps** | ❌ (2 steps only: 1 Trigger + 1 Action) | ✅ Supported |
| **Webhooks by Zapier (Custom HTTP POST)** | ❌ **Premium Feature (Paid Only)** | ✅ Supported |
| **Google Drive Trigger ("New File in Folder")** | ✅ Standard / Free | ✅ Supported |
| **Google Sheets Trigger/Action** | ✅ Standard / Free | ✅ Supported |

### The Free-Tier Bottleneck
Because **Webhooks by Zapier** is classified as a Premium application, a user on Zapier's Free tier cannot natively trigger an HTTP POST request with document binary data to a custom API endpoint.

### Recommended Approaches
1. **For 100% Free Automation**: Use the **Google Apps Script** recipe below. It is completely free, unlimited, native to Google Workspace, and requires zero paid subscriptions.
2. **For Organizations with Paid Zapier**: Use the **Zapier Webhook Action** recipe detailed in Section 4.

---

## 3. Recommended Free Alternative: Google Apps Script (Drive → Financial Agent)

This script monitors a specific Google Drive folder every 5 minutes (or on a timer) and sends new invoices and receipts directly to the Financial Assistant API with `auto_record=true`.

### Setup Instructions (3 minutes)

1. **Create a Folder in Google Drive**:
   - Name it `Impact Invoices & Receipts`.
   - Copy the Folder ID from the URL (the string after `folders/` in `https://drive.google.com/drive/folders/1ABCxyz...`).

2. **Open Google Apps Script**:
   - Go to [script.google.com](https://script.google.com/) and click **New Project**.
   - Name the project `Drive to Financial Agent`.

3. **Paste the Automation Script**:
   ```javascript
   // =========================================================================
   // Google Drive to Financial Agent Automation (100% Free)
   // =========================================================================
   const CONFIG = {
     API_ENDPOINT: "https://your-domain.com/api/v1/documents", // Your backend URL
     REVIEWER_TOKEN: "YOUR_REVIEWER_TOKEN_HERE",               // Same as REVIEWER_TOKEN in .env
     FOLDER_ID: "YOUR_GOOGLE_DRIVE_FOLDER_ID",               // Google Drive Folder ID
     PROJECT_ID: "Urban Climate Research",                     // Project name/ID
     PROCESSED_TAG: "[PROCESSED]"                             // Prefix added to processed files
   };

   function processNewInvoices() {
     const folder = DriveApp.getFolderById(CONFIG.FOLDER_ID);
     const files = folder.getFiles();

     while (files.hasNext()) {
       const file = files.next();
       const filename = file.getName();

       // Skip already processed documents
       if (filename.startsWith(CONFIG.PROCESSED_TAG)) {
         continue;
       }

       // Only process supported formats
       const mimeType = file.getMimeType();
       if (!["application/pdf", "image/jpeg", "image/png", "image/webp"].includes(mimeType)) {
         Logger.log("Skipping unsupported format: " + filename);
         continue;
       }

       try {
         Logger.log("Uploading file: " + filename);
         const blob = file.getBlob();

         const payload = {
           file: blob,
           project_id: CONFIG.PROJECT_ID,
           auto_record: "true"
         };

         const options = {
           method: "post",
           headers: {
             "Authorization": "Bearer " + CONFIG.REVIEWER_TOKEN
           },
           payload: payload,
           muteHttpExceptions: true
         };

         const response = UrlFetchApp.fetch(CONFIG.API_ENDPOINT, options);
         const resCode = response.getResponseCode();
         const resText = response.getContentText();

         if (resCode >= 200 && resCode < 300) {
           const result = JSON.parse(resText);
           Logger.log("Success! Document ID: " + result.document.id + " State: " + result.document.state);
           file.setName(CONFIG.PROCESSED_TAG + " " + filename);
         } else {
           Logger.log("Failed with status " + resCode + ": " + resText);
         }
       } catch (err) {
         Logger.log("Error processing " + filename + ": " + err.toString());
       }
     }
   }
   ```

4. **Set Up a Recurring Trigger**:
   - In Google Apps Script, click the **Triggers (Clock Icon)** on the left sidebar.
   - Click **Add Trigger** (bottom right).
   - Choose function: `processNewInvoices`.
   - Event source: `Time-driven` → `Minutes timer` → `Every 5 minutes` (or `Every 1 minute`).
   - Save.

Now, whenever anyone drops a receipt or PDF invoice into that Google Drive folder, it is automatically uploaded, verified, auto-recorded if valid, and renamed with `[PROCESSED]`.

---

## 4. Zapier Configuration (For Paid / Starter Plans)

If your organization has access to Zapier Premium Apps:

1. **Trigger**:
   - App: **Google Drive**
   - Event: **New File in Folder**
   - Select your target folder.

2. **Action**:
   - App: **Webhooks by Zapier**
   - Event: **Custom Request**
   - Method: `POST`
   - URL: `https://your-domain.com/api/v1/documents`
   - Data / Body:
     * `file`: Use the `File` (Hydrated file object) from Step 1.
     * `project_id`: `Urban Climate Research`
     * `auto_record`: `true`
   - Headers:
     * `Authorization`: `Bearer <REVIEWER_TOKEN>`
   - Test and turn on the Zap.

---

## 5. Google Sheets Integration Setup

When an expense is recorded (either automatically or through manual confirmation), the application immediately updates a Google Sheets spreadsheet.

You can connect Google Sheets using either of two methods:

### Option A: Google Apps Script Webhook (Recommended & Simplest)

1. Open your target Google Sheet.
2. In row 1, set the headers:
   `ID | Project | Category | Vendor | Date | Description | Amount | Currency`
3. Click **Extensions → Apps Script**.
4. Paste this webhook receiver:
   ```javascript
   function doPost(e) {
     try {
       const json = JSON.parse(e.postData.contents);
       const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
       const exp = json.expense;

       sheet.appendRow([
         exp.id,
         exp.project,
         exp.category,
         exp.vendor,
         exp.date,
         exp.description,
         exp.total,
         exp.currency
       ]);

       return ContentService.createTextOutput(JSON.stringify({status: "ok"}))
         .setMimeType(ContentService.MimeType.JSON);
     } catch (err) {
       return ContentService.createTextOutput(JSON.stringify({status: "error", error: err.toString()}))
         .setMimeType(ContentService.MimeType.JSON);
     }
   }
   ```
5. Click **Deploy → New Deployment**.
   - Type: **Web App**
   - Execute as: **Me**
   - Who has access: **Anyone**
   - Click Deploy and copy the **Web App URL**.
6. In your `.env` file on the backend server, add:
   ```ini
   SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/AKfycb.../exec
   ```
7. Restart the backend server. Every validated expense will now append into Google Sheets in real time.

### Option B: Google Sheets REST API v4

If you prefer using Google Cloud OAuth credentials:
1. In `.env`, set:
   ```ini
   SHEETS_SPREADSHEET_ID=1xYz...your_spreadsheet_id
   SHEETS_ACCESS_TOKEN=ya29...your_oauth_access_token
   ```
2. The application reserves row numbers sequentially and performs atomic upserts to `Expenses!A{row}:H{row}`.

---

## 6. How Users Can Inspect & Verify Integration Results

1. **Financial Overview Dashboard (`/`)**:
   - The metric card **"Google Sheets projection"** shows the live count of synced vs. failed deliveries.
2. **Operations & Audit Log (`/operations`)**:
   - Filter by stage `integration` to view exact timestamps, HTTP response codes, and retry counts for Google Sheets deliveries.
3. **Manual Re-Sync**:
   - In `/api/v1/expenses/{id}/sync`, users or administrators can manually trigger a retry if an external service temporarily dropped a connection.
