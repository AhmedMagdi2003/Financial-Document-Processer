-- Initial schema; apply once to an empty Supabase project as database owner.

-- Prefer: uv run python -m scripts.setup_db (also seeds categories/projects).


CREATE TABLE categories (
	id VARCHAR(80) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	definition TEXT NOT NULL, 
	active BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
)

;

ALTER TABLE "categories" ENABLE ROW LEVEL SECURITY;


CREATE TABLE content_items (
	id VARCHAR(36) NOT NULL, 
	source TEXT NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

ALTER TABLE "content_items" ENABLE ROW LEVEL SECURITY;


CREATE TABLE events (
	id VARCHAR(36) NOT NULL, 
	timestamp TIMESTAMP WITH TIME ZONE NOT NULL, 
	run_id VARCHAR(36), 
	request_id VARCHAR(36), 
	resource_id VARCHAR(36), 
	stage VARCHAR(80) NOT NULL, 
	operation VARCHAR(80) NOT NULL, 
	status VARCHAR(40) NOT NULL, 
	duration_ms INTEGER, 
	safe_metadata JSON NOT NULL, 
	error_code VARCHAR(80), 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_events_request_id ON events (request_id);

CREATE INDEX ix_events_resource_id ON events (resource_id);

CREATE INDEX ix_events_run_id ON events (run_id);

ALTER TABLE "events" ENABLE ROW LEVEL SECURITY;


CREATE TABLE llm_usage (
	id VARCHAR(36) NOT NULL, 
	run_id VARCHAR(36) NOT NULL, 
	provider VARCHAR(40) NOT NULL, 
	model VARCHAR(100) NOT NULL, 
	operation VARCHAR(50) NOT NULL, 
	input_tokens INTEGER, 
	output_tokens INTEGER, 
	cached_tokens INTEGER, 
	estimated_usd NUMERIC(16, 8), 
	details JSON NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_llm_usage_run_id ON llm_usage (run_id);

ALTER TABLE "llm_usage" ENABLE ROW LEVEL SECURITY;


CREATE TABLE projects (
	id VARCHAR(80) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	PRIMARY KEY (id)
)

;

ALTER TABLE "projects" ENABLE ROW LEVEL SECURITY;


CREATE TABLE content_revisions (
	id VARCHAR(80) NOT NULL, 
	content_id VARCHAR(36) NOT NULL, 
	number INTEGER NOT NULL, 
	drafts JSON NOT NULL, 
	digest VARCHAR(64) NOT NULL, 
	channels JSON NOT NULL, 
	decision VARCHAR(20) DEFAULT 'draft' NOT NULL, 
	decision_reason TEXT, 
	approved_by VARCHAR(100), 
	approved_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(content_id) REFERENCES content_items (id)
)

;

CREATE INDEX ix_content_revisions_content_id ON content_revisions (content_id);

ALTER TABLE "content_revisions" ENABLE ROW LEVEL SECURITY;


CREATE TABLE documents (
	id VARCHAR(36) NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	filename VARCHAR(250) NOT NULL, 
	project_id VARCHAR(80) NOT NULL, 
	uploader VARCHAR(100) NOT NULL, 
	storage_key TEXT NOT NULL, 
	mime VARCHAR(60) NOT NULL, 
	pages INTEGER NOT NULL, 
	state VARCHAR(40) NOT NULL, 
	version INTEGER NOT NULL, 
	candidate JSON, 
	error_code VARCHAR(80), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (sha256), 
	FOREIGN KEY(project_id) REFERENCES projects (id)
)

;

CREATE INDEX ix_documents_state ON documents (state);

ALTER TABLE "documents" ENABLE ROW LEVEL SECURITY;


CREATE TABLE expenses (
	id VARCHAR(36) NOT NULL, 
	document_id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(80) NOT NULL, 
	category_id VARCHAR(80), 
	vendor VARCHAR(250), 
	vendor_normalized VARCHAR(250) NOT NULL, 
	document_number VARCHAR(150), 
	date VARCHAR(10), 
	description TEXT NOT NULL, 
	total NUMERIC(20, 4) NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	confirmed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (document_id), 
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(category_id) REFERENCES categories (id)
)

;

CREATE INDEX ix_expenses_currency ON expenses (currency);

CREATE INDEX ix_expenses_date ON expenses (date);

CREATE INDEX ix_expenses_document_number ON expenses (document_number);

CREATE INDEX ix_expenses_project_id ON expenses (project_id);

CREATE INDEX ix_expenses_vendor_normalized ON expenses (vendor_normalized);

ALTER TABLE "expenses" ENABLE ROW LEVEL SECURITY;


CREATE TABLE extraction_attempts (
	id VARCHAR(36) NOT NULL, 
	document_id VARCHAR(36) NOT NULL, 
	run_id VARCHAR(36) NOT NULL, 
	route VARCHAR(40) NOT NULL, 
	reason TEXT NOT NULL, 
	candidate JSON, 
	status VARCHAR(40) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(document_id) REFERENCES documents (id)
)

;

CREATE INDEX ix_extraction_attempts_document_id ON extraction_attempts (document_id);

CREATE INDEX ix_extraction_attempts_run_id ON extraction_attempts (run_id);

ALTER TABLE "extraction_attempts" ENABLE ROW LEVEL SECURITY;


CREATE TABLE idempotency_keys (
	key VARCHAR(200) NOT NULL, 
	fingerprint VARCHAR(64) NOT NULL, 
	document_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (key), 
	FOREIGN KEY(document_id) REFERENCES documents (id)
)

;

ALTER TABLE "idempotency_keys" ENABLE ROW LEVEL SECURITY;


CREATE TABLE publications (
	id VARCHAR(150) NOT NULL, 
	revision_id VARCHAR(80) NOT NULL, 
	channel VARCHAR(40) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	attempts INTEGER NOT NULL, 
	url TEXT, 
	published_at TIMESTAMP WITH TIME ZONE, 
	error VARCHAR(120), 
	PRIMARY KEY (id), 
	FOREIGN KEY(revision_id) REFERENCES content_revisions (id)
)

;

CREATE INDEX ix_publications_revision_id ON publications (revision_id);

ALTER TABLE "publications" ENABLE ROW LEVEL SECURITY;


CREATE TABLE validation_issues (
	id VARCHAR(36) NOT NULL, 
	document_id VARCHAR(36) NOT NULL, 
	code VARCHAR(80) NOT NULL, 
	severity VARCHAR(30) NOT NULL, 
	field VARCHAR(80) NOT NULL, 
	explanation TEXT NOT NULL, 
	evidence JSON NOT NULL, 
	resolution TEXT, 
	resolved_by VARCHAR(100), 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(document_id) REFERENCES documents (id)
)

;

CREATE INDEX ix_validation_issues_document_id ON validation_issues (document_id);

ALTER TABLE "validation_issues" ENABLE ROW LEVEL SECURITY;


CREATE TABLE integration_deliveries (
	id VARCHAR(80) NOT NULL, 
	expense_id VARCHAR(36) NOT NULL, 
	row_number INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	attempts INTEGER NOT NULL, 
	error VARCHAR(80), 
	PRIMARY KEY (id), 
	UNIQUE (expense_id), 
	FOREIGN KEY(expense_id) REFERENCES expenses (id), 
	UNIQUE (row_number)
)

;

ALTER TABLE "integration_deliveries" ENABLE ROW LEVEL SECURITY;