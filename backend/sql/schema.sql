-- BigQuery schema for the Nairobi County budget knowledge base.
--
-- Run these statements against the dataset configured by Config.BQ_DATASET
-- (default: county_budget) in location Config.BQ_LOCATION (default: US).
-- Replace `your_project.county_budget` below with the fully qualified
-- dataset identifier for your environment, or rely on the Python helper
-- `app.services.bq.ensure_dataset_and_tables()` which mirrors this DDL.
--
-- The dataset itself must already exist; create it with:
--   CREATE SCHEMA IF NOT EXISTS `your_project.county_budget`
--     OPTIONS(location = "US");

-- ---------------------------------------------------------------------------
-- budget_chunks: one row per ~500-800 token chunk from the parsed PDF.
--
-- Notes on the embedding column:
--   embedding is ARRAY<FLOAT64> (a REPEATED FLOAT64 field in BigQuery terms).
--   Vertex AI text-embedding-004 emits 768-dimensional vectors, so every
--   row written by this pipeline will have length 768. BigQuery itself does
--   not enforce array length, so the schema stays permissive: if we ever
--   swap embedding models the column does not need to change.
--   Vector retrieval is done via BigQuery's VECTOR_SEARCH TVF with
--   distance_type => 'COSINE' (see app/services/bq.py::vector_search).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `your_project.county_budget.budget_chunks` (
  -- Identity and provenance for each chunk:
  chunk_id     STRING    NOT NULL,
  page_number  INT64,
  section      STRING,
  ward         STRING,
  text         STRING,
  doc_id       STRING,

  -- Vector column: ARRAY<FLOAT64>, 768 dims for text-embedding-004.
  embedding    ARRAY<FLOAT64>,

  -- Ingest timestamp; defaults to now so streaming inserts can omit it.
  inserted_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- ---------------------------------------------------------------------------
-- budget_documents: one row per ingested source PDF, for provenance and
-- versioning. A chunk in budget_chunks references this via doc_id.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `your_project.county_budget.budget_documents` (
  -- Stable identifier for the source document (e.g. a slug or hash):
  doc_id       STRING    NOT NULL,
  source_url   STRING,

  -- When the PDF was ingested and which logical version it represents:
  ingested_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  version      STRING
);
