-- PostgreSQL reference schema generated from backend/app/models.py.

CREATE TABLE evidence (
	id SERIAL NOT NULL,
	symbol VARCHAR(30),
	title TEXT NOT NULL,
	url TEXT NOT NULL,
	body VARCHAR(2000) NOT NULL,
	published_at VARCHAR(32) NOT NULL,
	ingested_at VARCHAR(32) NOT NULL,
	sentiment FLOAT NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (url)
);

CREATE TABLE improvements (
	id SERIAL NOT NULL,
	title VARCHAR(200) NOT NULL,
	detail TEXT NOT NULL,
	status VARCHAR(30) NOT NULL,
	created_at VARCHAR(32) NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE instruments (
	symbol VARCHAR(30) NOT NULL,
	name VARCHAR(120) NOT NULL,
	sector VARCHAR(80) NOT NULL,
	kind VARCHAR(20) NOT NULL,
	member_from VARCHAR(10) NOT NULL,
	member_to VARCHAR(10),
	PRIMARY KEY (symbol)
);

CREATE TABLE job_runs (
	id SERIAL NOT NULL,
	job VARCHAR(80) NOT NULL,
	status VARCHAR(30) NOT NULL,
	rows INTEGER NOT NULL,
	detail TEXT NOT NULL,
	started_at VARCHAR(32) NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE model_versions (
	name VARCHAR(80) NOT NULL,
	status VARCHAR(30) NOT NULL,
	created_at VARCHAR(32) NOT NULL,
	description TEXT NOT NULL,
	brier FLOAT,
	PRIMARY KEY (name)
);

CREATE TABLE news_articles (
	id SERIAL NOT NULL,
	source VARCHAR(60) NOT NULL,
	url TEXT NOT NULL,
	title TEXT NOT NULL,
	body VARCHAR(2000) NOT NULL,
	content_hash VARCHAR(64) NOT NULL,
	published_at VARCHAR(32) NOT NULL,
	received_at VARCHAR(32) NOT NULL,
	time_basis VARCHAR(60) NOT NULL,
	symbols TEXT NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (url, content_hash)
);

CREATE INDEX ix_news_articles_published_at ON news_articles (published_at);

CREATE TABLE raw_records (
	id SERIAL NOT NULL,
	source TEXT NOT NULL,
	payload TEXT NOT NULL,
	received_at VARCHAR(32) NOT NULL,
	status VARCHAR(30) NOT NULL,
	reason TEXT,
	PRIMARY KEY (id)
);

CREATE TABLE scheduled_runs (
	key VARCHAR(100) NOT NULL,
	status VARCHAR(20) NOT NULL,
	attempts INTEGER NOT NULL,
	updated_at VARCHAR(32) NOT NULL,
	detail TEXT NOT NULL,
	PRIMARY KEY (key)
);

CREATE TABLE settings (
	key VARCHAR(80) NOT NULL,
	value TEXT NOT NULL,
	PRIMARY KEY (key)
);

CREATE TABLE token_budgets (
	date VARCHAR(10) NOT NULL,
	reserved INTEGER NOT NULL,
	PRIMARY KEY (date)
);

CREATE TABLE instrument_mappings (
	symbol VARCHAR(30) NOT NULL,
	instrument_key VARCHAR(100) NOT NULL,
	provider VARCHAR(30) NOT NULL,
	PRIMARY KEY (symbol),
	FOREIGN KEY(symbol) REFERENCES instruments (symbol),
	UNIQUE (instrument_key)
);

CREATE TABLE predictions (
	id SERIAL NOT NULL,
	symbol VARCHAR(30) NOT NULL,
	date VARCHAR(10) NOT NULL,
	data_cutoff VARCHAR(32) NOT NULL,
	horizon VARCHAR(30) NOT NULL,
	direction VARCHAR(8) NOT NULL,
	prob_up FLOAT NOT NULL,
	expected_low FLOAT NOT NULL,
	expected_high FLOAT NOT NULL,
	invalidation FLOAT NOT NULL,
	ref_price FLOAT NOT NULL,
	rank INTEGER,
	rationale TEXT NOT NULL,
	model_version VARCHAR(80) NOT NULL,
	sources TEXT NOT NULL,
	allocation FLOAT NOT NULL,
	cost_rate FLOAT NOT NULL,
	synthetic BOOLEAN NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (date, symbol, model_version, horizon),
	CHECK (prob_up >= 0 AND prob_up <= 1),
	CHECK (direction IN ('UP','DOWN')),
	FOREIGN KEY(symbol) REFERENCES instruments (symbol)
);

CREATE INDEX ix_predictions_date ON predictions (date);

CREATE TABLE prices (
	id SERIAL NOT NULL,
	symbol VARCHAR(30) NOT NULL,
	date VARCHAR(10) NOT NULL,
	open FLOAT NOT NULL,
	high FLOAT NOT NULL,
	low FLOAT NOT NULL,
	close FLOAT NOT NULL,
	volume INTEGER NOT NULL,
	published_at VARCHAR(32) NOT NULL,
	ingested_at VARCHAR(32) NOT NULL,
	source TEXT NOT NULL,
	synthetic BOOLEAN NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (symbol, date),
	CHECK (open > 0 AND close > 0 AND high >= low),
	FOREIGN KEY(symbol) REFERENCES instruments (symbol)
);

CREATE INDEX ix_prices_date ON prices (date);

CREATE TABLE quotes (
	symbol VARCHAR(30) NOT NULL,
	price FLOAT NOT NULL,
	change FLOAT NOT NULL,
	market_at VARCHAR(32) NOT NULL,
	received_at VARCHAR(32) NOT NULL,
	provider VARCHAR(30) NOT NULL,
	PRIMARY KEY (symbol),
	FOREIGN KEY(symbol) REFERENCES instruments (symbol)
);

CREATE TABLE resolutions (
	prediction_id INTEGER NOT NULL,
	entry FLOAT NOT NULL,
	exit FLOAT NOT NULL,
	"right" BOOLEAN,
	pnl FLOAT,
	baseline_pnl FLOAT,
	costs FLOAT NOT NULL,
	cause VARCHAR(50),
	explanation TEXT,
	resolved_at VARCHAR(32) NOT NULL,
	PRIMARY KEY (prediction_id),
	FOREIGN KEY(prediction_id) REFERENCES predictions (id)
);

CREATE OR REPLACE FUNCTION reject_record_change() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Recorded calls and results cannot be changed'; END; $$;

CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON predictions FOR EACH ROW EXECUTE FUNCTION reject_record_change();

CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON resolutions FOR EACH ROW EXECUTE FUNCTION reject_record_change();
