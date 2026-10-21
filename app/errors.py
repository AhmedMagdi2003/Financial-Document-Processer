"""Structured human-friendly error catalog and mapping for the financial assistant.

Translates internal errors, provider exceptions, validation codes, and edge cases
into structured messages that explain:
1. What failed
2. Why it failed
3. What the user can do next
Without leaking sensitive tokens, database connection details, or technical stack traces.
"""

import re
from dataclasses import asdict, dataclass
from typing import Literal

ErrorCategory = Literal[
    "ai_extraction",
    "unreadable_document",
    "missing_fields",
    "validation_warning",
    "api_failure",
    "system_error",
]

ErrorSeverity = Literal["blocking", "review", "warning"]


@dataclass(frozen=True)
class HumanError:
    code: str
    category: ErrorCategory
    title: str
    reason: str
    action: str
    severity: ErrorSeverity
    can_retry: bool = False
    can_edit: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


ERROR_CATALOG: dict[str, HumanError] = {
    # 1. AI Extraction Failures
    "MODEL_CALL_FAILED": HumanError(
        code="MODEL_CALL_FAILED",
        category="ai_extraction",
        title="AI Extraction Interrupted",
        reason=(
            "The AI vision model encountered a temporary timeout or connection "
            "error while reading the document."
        ),
        action=(
            "Click 'Re-extract' to try again, or enter document details manually "
            "using the edit form."
        ),
        severity="blocking",
        can_retry=True,
        can_edit=True,
    ),
    "MODEL_NOT_CONFIGURED": HumanError(
        code="MODEL_NOT_CONFIGURED",
        category="ai_extraction",
        title="Extraction Model Not Configured",
        reason="No AI model is configured for this workspace.",
        action=(
            "Check environment configuration (e.g. set PROVIDER and MODEL_NAME in .env) "
            "or use fixture replay."
        ),
        severity="blocking",
        can_retry=False,
        can_edit=True,
    ),
    "PROVIDER_NOT_CONFIGURED": HumanError(
        code="PROVIDER_NOT_CONFIGURED",
        category="ai_extraction",
        title="AI Provider Unavailable",
        reason="The configured AI provider credentials are missing or uninitialized.",
        action="Provide a valid API key for your chosen AI provider in server settings.",
        severity="blocking",
        can_retry=False,
        can_edit=True,
    ),
    "INPUT_CONTEXT_LIMIT": HumanError(
        code="INPUT_CONTEXT_LIMIT",
        category="ai_extraction",
        title="Document Exceeds Model Length Limit",
        reason="The document contains more text than the active AI model can process in one pass.",
        action="Upload a shorter excerpt (8 pages or fewer) or input key totals manually.",
        severity="blocking",
        can_retry=False,
        can_edit=True,
    ),
    "JOB_COST_GUARD": HumanError(
        code="JOB_COST_GUARD",
        category="ai_extraction",
        title="Job Cost Guard Triggered",
        reason="The estimated token cost for processing exceeds the safety threshold.",
        action="Review the document size or adjust MAX_JOB_COST_USD in system settings.",
        severity="blocking",
        can_retry=False,
        can_edit=True,
    ),
    "LLM_CALL_LIMIT": HumanError(
        code="LLM_CALL_LIMIT",
        category="ai_extraction",
        title="Model Call Limit Reached",
        reason=(
            "The maximum allowed AI model attempts (3) was reached without concluding extraction."
        ),
        action="Edit extracted fields manually or inspect document image clarity before retrying.",
        severity="blocking",
        can_retry=True,
        can_edit=True,
    ),
    "UNSUPPORTED_CAPABILITY_XAI_VISION": HumanError(
        code="UNSUPPORTED_CAPABILITY_XAI_VISION",
        category="ai_extraction",
        title="Vision Not Supported by Active Provider",
        reason="The configured model provider does not support direct image/scanned PDF vision.",
        action="Switch to Gemini or OpenAI for scanned receipts, or upload a digital text PDF.",
        severity="blocking",
        can_retry=False,
        can_edit=True,
    ),
    "RESOURCE_EXHAUSTED": HumanError(
        code="RESOURCE_EXHAUSTED",
        category="ai_extraction",
        title="AI Provider Quota Reached",
        reason="The provider's rate limit or free-tier daily quota was reached.",
        action=(
            "Wait for quota renewal, switch to a production model (e.g. gemini-2.5-flash), "
            "or enter details manually."
        ),
        severity="blocking",
        can_retry=True,
        can_edit=True,
    ),

    # 2. Unreadable / Invalid Documents
    "FILE_REJECTED": HumanError(
        code="FILE_REJECTED",
        category="unreadable_document",
        title="Unsupported or Corrupted File",
        reason="The file could not be verified as a valid PDF or supported image (PNG/JPEG/WEBP).",
        action="Ensure the file is not password-protected, corrupted, or empty, and re-upload.",
        severity="blocking",
        can_retry=False,
        can_edit=False,
    ),
    "CORRUPTED_PDF": HumanError(
        code="CORRUPTED_PDF",
        category="unreadable_document",
        title="Corrupted PDF Document",
        reason="The uploaded PDF header is damaged or missing required page structures.",
        action="Re-save or print-to-PDF the document from your viewer and upload the new copy.",
        severity="blocking",
        can_retry=False,
        can_edit=False,
    ),
    "FILE_TOO_LARGE": HumanError(
        code="FILE_TOO_LARGE",
        category="unreadable_document",
        title="File Exceeds Size Limit",
        reason="The document exceeds the 10 MB maximum upload limit.",
        action="Compress the document or split it into smaller sections under 10 MB.",
        severity="blocking",
        can_retry=False,
        can_edit=False,
    ),
    "PAGE_LIMIT_EXCEEDED": HumanError(
        code="PAGE_LIMIT_EXCEEDED",
        category="unreadable_document",
        title="Page Limit Exceeded",
        reason="The document exceeds the 8-page maximum allowed for this prototype.",
        action="Extract the relevant invoice/receipt page and re-upload.",
        severity="blocking",
        can_retry=False,
        can_edit=False,
    ),
    "EMPTY_FILE": HumanError(
        code="EMPTY_FILE",
        category="unreadable_document",
        title="Empty File Uploaded",
        reason="The uploaded file contains zero bytes.",
        action="Select a valid file from your device and re-upload.",
        severity="blocking",
        can_retry=False,
        can_edit=False,
    ),

    # 3. Missing Required Financial Fields (Critical Conditions 1 & 2)
    "MISSING_GRAND_TOTAL": HumanError(
        code="MISSING_GRAND_TOTAL",
        category="missing_fields",
        title="Grand Total Missing",
        reason="The document does not explicitly state a final payable grand total.",
        action="Locate the total on the original document and type it into the Grand Total field.",
        severity="blocking",
        can_retry=False,
        can_edit=True,
    ),
    "MISSING_CURRENCY": HumanError(
        code="MISSING_CURRENCY",
        category="missing_fields",
        title="Currency Code Missing",
        reason="No currency symbol or 3-letter ISO code was identified on the document.",
        action=(
            "Enter 3-letter currency code (e.g. USD, EUR, EGP) in the currency field."
        ),
        severity="blocking",
        can_retry=False,
        can_edit=True,
    ),

    # 4. Critical Conditions 3 & 4 (Review Required)
    "TOTAL_INCONSISTENCY": HumanError(
        code="TOTAL_INCONSISTENCY",
        category="validation_warning",
        title="Arithmetic Inconsistency Detected",
        reason=(
            "The printed line items, subtotal, tax, or discount do not sum to the "
            "stated grand total."
        ),
        action=(
            "Review the arithmetic discrepancy. Either correct the numbers or provide "
            "a justification note to confirm."
        ),
        severity="review",
        can_retry=False,
        can_edit=True,
    ),
    "ARITHMETIC_MISMATCH": HumanError(
        code="ARITHMETIC_MISMATCH",
        category="validation_warning",
        title="Arithmetic Inconsistency Detected",
        reason="The printed subtotal, tax, and discount arithmetic conflicts with the grand total.",
        action="Review the original numbers and supply a brief justification to accept total.",
        severity="review",
        can_retry=False,
        can_edit=True,
    ),
    "POSSIBLE_DUPLICATE": HumanError(
        code="POSSIBLE_DUPLICATE",
        category="validation_warning",
        title="Potential Duplicate Expense",
        reason=(
            "Another document in the workspace shares the same invoice number or identical "
            "vendor, date, currency, and amount."
        ),
        action=(
            "Inspect the matching record links. If legitimately distinct, provide a "
            "10+ character explanation to confirm."
        ),
        severity="review",
        can_retry=False,
        can_edit=True,
    ),

    # 5. Nonblocking Warnings
    "VENDOR_UNKNOWN": HumanError(
        code="VENDOR_UNKNOWN",
        category="validation_warning",
        title="Vendor Name Unclear",
        reason="The vendor or merchant name could not be reliably extracted from the header.",
        action="Optional: Enter the vendor name for cleaner reporting.",
        severity="warning",
        can_retry=False,
        can_edit=True,
    ),
    "DATE_UNKNOWN": HumanError(
        code="DATE_UNKNOWN",
        category="validation_warning",
        title="Document Date Missing",
        reason="No document date was recognized.",
        action="Optional: Pick the transaction date to place the expense in the correct month.",
        severity="warning",
        can_retry=False,
        can_edit=True,
    ),
    "DATE_IMPLAUSIBLE": HumanError(
        code="DATE_IMPLAUSIBLE",
        category="validation_warning",
        title="Date Needs Verification",
        reason="The extracted date is either in the future or prior to the year 2000.",
        action="Confirm the date against the receipt and update if necessary.",
        severity="warning",
        can_retry=False,
        can_edit=True,
    ),
    "CATEGORY_UNKNOWN": HumanError(
        code="CATEGORY_UNKNOWN",
        category="validation_warning",
        title="Category Suggestion Ambiguous",
        reason="The model could not identify a clear matching category from the active list.",
        action="Select an appropriate budget category from the dropdown menu.",
        severity="warning",
        can_retry=False,
        can_edit=True,
    ),

    # 6. Integrations & Storage
    "STORAGE_UPLOAD_FAILED": HumanError(
        code="STORAGE_UPLOAD_FAILED",
        category="api_failure",
        title="Original Document Storage Error",
        reason="Failed to archive the original file in private document storage.",
        action="Check storage permissions and cloud credentials in environment settings.",
        severity="blocking",
        can_retry=True,
        can_edit=False,
    ),
    "SHEETS_NOT_CONFIGURED": HumanError(
        code="SHEETS_NOT_CONFIGURED",
        category="api_failure",
        title="Google Sheets Integration Inactive",
        reason="Google Sheets synchronization is not configured for this workspace.",
        action="Add SHEETS_SPREADSHEET_ID and access token, or use the webhook integration.",
        severity="warning",
        can_retry=False,
        can_edit=False,
    ),
}

DEFAULT_ERROR = HumanError(
    code="UNKNOWN_ERROR",
    category="system_error",
    title="Unexpected Processing Issue",
    reason="The application encountered an unexpected situation while processing the request.",
    action="Check the Activity & Operations log for details, or retry the operation.",
    severity="blocking",
    can_retry=True,
    can_edit=True,
)


def map_error(code_or_message: str | Exception | None) -> HumanError:
    """Safely map any error code, exception, or validation issue into a HumanError.

    Ensures technical internals (SDK modules, stack lines, database URLs) are scrubbed.
    """
    if code_or_message is None:
        return DEFAULT_ERROR

    code = str(code_or_message).strip()

    # Direct match in catalog
    if code in ERROR_CATALOG:
        return ERROR_CATALOG[code]

    upper = code.upper()

    # AI SDK / Model error checks
    if "429" in upper or "QUOTA" in upper or "RESOURCE_EXHAUSTED" in upper:
        return ERROR_CATALOG["RESOURCE_EXHAUSTED"]
    if (
        "GENAI" in upper
        or "OPENAI" in upper
        or "MODEL" in upper
        or "TIMEOUT" in upper
        or "CALL_FAILED" in upper
        or "DEADLINE" in upper
        or "INVALID_ARGUMENT" in upper
    ):
        return ERROR_CATALOG["MODEL_CALL_FAILED"]
    if "PDF" in upper or "CORRUPT" in upper or "UNSUPPORTED" in upper:
        return ERROR_CATALOG["CORRUPTED_PDF"]
    if "PAGE" in upper and "LIMIT" in upper:
        return ERROR_CATALOG["PAGE_LIMIT_EXCEEDED"]
    if "SIZE" in upper or "LARGE" in upper or "BYTES" in upper:
        return ERROR_CATALOG["FILE_TOO_LARGE"]
    if "SHEETS" in upper:
        return ERROR_CATALOG["SHEETS_NOT_CONFIGURED"]
    if "STORAGE" in upper:
        return ERROR_CATALOG["STORAGE_UPLOAD_FAILED"]

    # Sanitize any technical substrings
    sanitized = re.sub(
        r"[a-zA-Z0-9_\.]+\.(errors|client|models|views)[^\s]*",
        "System Component",
        code,
    )
    sanitized = re.sub(r"(https?://\S+|postgres\S+|Bearer\s+\S+)", "[redacted]", sanitized)

    return HumanError(
        code=code[:50] or "PROCESSING_ERROR",
        category="system_error",
        title="Processing Issue",
        reason="An unexpected issue occurred while analyzing the document.",
        action="Verify document format or try again. Technical details are logged in Operations.",
        severity="blocking",
        can_retry=True,
        can_edit=True,
    )
