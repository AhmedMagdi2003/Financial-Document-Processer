# Hosting & Automation Setup Guide: Render, ngrok, Google Apps Script, and Make.com

This guide covers:
1. **Hosting Switcher:** Deploying 24/7 on **Render** or tunneling locally with **ngrok**, switchable via `.env`.
2. **100% Free Native Google Ingestion:** Watching Google Drive and syncing with Google Sheets using Apps Script (0$ forever).
3. **Make.com Visual Workflow:** Importing our ready-to-use scenario blueprint for 1,000 free operations/month.

---

## Part 1: Public Hosting (Render vs ngrok)

External services (Google Apps Script, Make.com, Zapier) need a public HTTPS address to send document files to your backend.

### 1. The `.env` Hosting Switcher

In your project `.env` file, configure your hosting provider:

```ini
# --- Hosting Switcher: "render", "ngrok", or "local" ---
HOSTING_PROVIDER=render

# Render Cloud URL (when deployed)
RENDER_URL=https://financial-document-processor.onrender.com

# ngrok Tunnel URL (when running locally)
NGROK_URL=https://your-ngrok-tunnel.ngrok-free.app

# Optional override:
PUBLIC_BASE_URL=
```

- When `HOSTING_PROVIDER=render`, the application resolves to `RENDER_URL`.
- When `HOSTING_PROVIDER=ngrok`, the application resolves to `NGROK_URL`.
- You can inspect the current active URL anytime at `http://127.0.0.1:8000/integrations`.

---

### Option A: Deploy on Render.com (24/7 Cloud Hosting)

1. **Push your code to GitHub**:
   - Create a repository on GitHub (private or public) and push `Financial-Document-Processer`.
2. **Create a Free Web Service on Render**:
   - Go to [dashboard.render.com](https://dashboard.render.com) and click **New + > Web Service**.
   - Connect your GitHub repository.
   - **Environment:** `Python`
   - **Region:** Frankfurt (or closest to you)
   - **Build Command:** `pip install uv && uv sync --frozen`
   - **Start Command:** `uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** `Free`
3. **Add Environment Variables in Render**:
   - `MODE`: `cloud`
   - `HOSTING_PROVIDER`: `render`
   - `DATABASE_URL`: Your Supabase PostgreSQL URL
   - `SUPABASE_URL`: Your Supabase project URL
   - `REVIEWER_TOKEN`: A secure random string (minimum 24 chars)
   - `SESSION_SECRET`: A secure random string (minimum 24 chars)
   - `SECURE_COOKIES`: `false`
   - `AUTO_RECORD`: `true`
   - `PROVIDER`: `gemini`
   - `GOOGLE_API_KEY`: Your Google AI Studio API key
   - `MODEL_NAME`: `gemini-2.0-flash`
   - `INPUT_USD_PER_MILLION`: `0.10`
   - `OUTPUT_USD_PER_MILLION`: `0.40`
   - `PRICING_SOURCE_URL`: `https://ai.google.dev/pricing`
   - `PRICING_CHECKED_AT`: `2026-10-21`
4. **Deploy**:
   - Render will build the project and assign a public HTTPS domain:  
     `https://your-app-name.onrender.com`.
   - Update `RENDER_URL=https://your-app-name.onrender.com` in your local `.env`.

---

### Option B: Run Locally with ngrok Tunnel

If you want to keep the server running on your computer:

1. **Install ngrok** (if not already installed):
   ```powershell
   winget install ngrok.ngrok
   ```
2. **Connect your free ngrok account** (from [dashboard.ngrok.com](https://dashboard.ngrok.com)):
   ```powershell
   ngrok config add-authtoken <YOUR_NGROK_AUTH_TOKEN>
   ```
3. **Run the automated tunnel helper**:
   ```powershell
   cd D:\ImpactCircles\Financial-Document-Processer
   uv run python scripts/start_tunnel.py
   ```
   *The helper automatically starts ngrok, queries its active public URL, and updates `NGROK_URL` and `HOSTING_PROVIDER=ngrok` in your `.env`!*

---

## Part 2: Automation Integrations

### Method 1: Google Apps Script (100% Free Forever, No Third-Party Tools)

#### Step 1: Set up Google Sheets Auto-Sync
1. Open Google Drive, create a new Google Sheet named **Impact Financial Records**.
2. Rename the first tab to **Expenses**.
3. In row 1, set the 8 headers:
   `ID` | `Project` | `Category` | `Vendor` | `Date` | `Description` | `Amount` | `Currency`
4. Click **Extensions > Apps Script**.
5. Delete any code and paste the contents of `scripts/google_apps_script/SheetsWebhook.gs`.
6. Click the gear icon (**Project Settings**), scroll to **Script Properties**, and add:
   - `SPREADSHEET_ID`: (The ID string in your spreadsheet URL between `/d/` and `/edit`)
   - `SHEETS_WEBHOOK_SECRET`: (Any secure random string of 24+ characters)
7. Click **Deploy > New Deployment**:
   - **Select type:** Web app
   - **Execute as:** Me
   - **Who has access:** Anyone
   - Click **Deploy** and copy the **Web app URL** (`https://script.google.com/macros/s/.../exec`).
8. Add this URL to your `.env`:
   ```ini
   SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec
   SHEETS_WEBHOOK_SECRET=your_secret_from_step_6
   ```

---

#### Step 2: Set up Google Drive Auto-Ingestion
1. Create a folder in Google Drive (e.g. **Incoming Invoices**).
2. Copy the **Folder ID** from your browser address bar (the string after `folders/`).
3. Open [script.google.com](https://script.google.com) and click **New Project**.
4. Paste the contents of `scripts/google_apps_script/DriveIngestion.gs`.
5. Go to **Project Settings > Script Properties** and add:
   - `API_BASE_URL`: Your active public URL (`https://your-app.onrender.com` or `https://your-ngrok.ngrok-free.app`)
   - `REVIEWER_TOKEN`: The `REVIEWER_TOKEN` from your `.env`
   - `FOLDER_ID`: The Google Drive folder ID from Step 2
   - `PROJECT_ID`: An existing project ID (e.g. `river` or `fictional-corp`)
   - `AUTO_RECORD`: `true`
6. In the function dropdown, select `processNewInvoices` and click **Run** to grant Google Drive permissions.
7. In the dropdown, select `installDriveTrigger` and click **Run**.
   *This schedules the poller to check your Google Drive folder every 1 minute automatically!*
8. **Test it:** Drop a PDF invoice into your Google Drive folder. The next poll attempts upload and extraction; whether it is recorded depends on validation and the configured review policy. A confirmed expense can then sync to Google Sheets.

---

### Method 2: Make.com Integration (Visual Drag & Drop, 1,000 Free Operations/Month)

Make.com (formerly Integromat) allows visual workflows and includes **Webhooks and HTTP Multipart requests for free** (unlike Zapier, which charges for webhooks).

#### Step 1: Download the Ready Blueprint
We have generated a pre-configured scenario blueprint file:  
`scripts/make/google_drive_to_finance_blueprint.json` (or download it from your server at `/api/v1/integrations/scripts/google_drive_to_finance_blueprint.json`).

#### Step 2: Import into Make.com
1. Go to [make.com](https://www.make.com) and sign in to your free account.
2. Click **Scenarios > Create a new scenario**.
3. In the bottom toolbar, click the **... (More)** icon and choose **Import Blueprint**.
4. Upload `scripts/make/google_drive_to_finance_blueprint.json`.
5. You will see 3 connected modules:
   - **Module 1 (Google Drive - Watch Files):** Click it, connect your Google account, and select your Google Drive folder.
   - **Module 2 (Google Drive - Download a File):** Automatically receives the file from Module 1.
   - **Module 3 (HTTP - Make a Multipart/form-data request):**
     - **URL:** Replace `REPLACE_WITH_YOUR_HOST_URL` with your active public URL (`https://your-app.onrender.com` or `https://your-ngrok.ngrok-free.app`).
     - **Headers:** Replace `REPLACE_WITH_YOUR_REVIEWER_TOKEN` with your server's `REVIEWER_TOKEN`.
     - **Body fields:** Keep `project_id: river`, `auto_record: true`, and `file: {{2.data}}`.
6. Click **Save** (disk icon at the bottom).
7. Toggle the switch at the bottom left to **ON** (scheduling: e.g. every 15 minutes).
8. Click **Run once** to test with an invoice in your Google Drive folder.
