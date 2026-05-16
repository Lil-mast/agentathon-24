from __future__ import annotations

import logging
from typing import Any

from google.cloud import bigquery

from app.config import Config

logger = logging.getLogger(__name__)

# Module-level singleton; built lazily so importing this module never blocks
# on missing credentials.
_BQ_CLIENT: bigquery.Client | None = None

CHUNKS_TABLE = "budget_chunks"
DOCUMENTS_TABLE = "budget_documents"


def _client() -> bigquery.Client:
    """Return a process-wide BigQuery client, constructing it on first use."""
    global _BQ_CLIENT
    if _BQ_CLIENT is None:
        logger.debug(
            "Constructing BigQuery client (project=%s, location=%s)",
            Config.GCP_PROJECT_ID,
            Config.BQ_LOCATION,
        )
        _BQ_CLIENT = bigquery.Client(
            project=Config.GCP_PROJECT_ID,
            location=Config.BQ_LOCATION,
        )
    return _BQ_CLIENT


def _dataset_ref() -> str:
    return f"{Config.GCP_PROJECT_ID}.{Config.BQ_DATASET}"


def _table_ref(table_name: str) -> str:
    return f"{_dataset_ref()}.{table_name}"


def _chunks_schema() -> list[bigquery.SchemaField]:
    return [
        bigquery.SchemaField("chunk_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("page_number", "INT64", mode="NULLABLE"),
        bigquery.SchemaField("section", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("ward", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("text", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("doc_id", "STRING", mode="NULLABLE"),
        # Vector column: REPEATED FLOAT64 (i.e. ARRAY<FLOAT64>). BigQuery does
        # not enforce array length; Vertex text-embedding-004 emits 768 dims.
        bigquery.SchemaField("embedding", "FLOAT64", mode="REPEATED"),
        bigquery.SchemaField(
            "inserted_at",
            "TIMESTAMP",
            mode="NULLABLE",
            default_value_expression="CURRENT_TIMESTAMP()",
        ),
    ]


def _documents_schema() -> list[bigquery.SchemaField]:
    return [
        bigquery.SchemaField("doc_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("source_url", "STRING", mode="NULLABLE"),
        bigquery.SchemaField(
            "ingested_at",
            "TIMESTAMP",
            mode="NULLABLE",
            default_value_expression="CURRENT_TIMESTAMP()",
        ),
        bigquery.SchemaField("version", "STRING", mode="NULLABLE"),
    ]


def ensure_dataset_and_tables() -> None:
    """Create the dataset and both tables if they do not already exist."""
    client = _client()

    dataset = bigquery.Dataset(_dataset_ref())
    dataset.location = Config.BQ_LOCATION
    dataset = client.create_dataset(dataset, exists_ok=True)
    logger.info("Ensured dataset %s exists in %s", dataset.dataset_id, dataset.location)

    chunks_table = bigquery.Table(_table_ref(CHUNKS_TABLE), schema=_chunks_schema())
    chunks_table = client.create_table(chunks_table, exists_ok=True)
    logger.info("Ensured table %s exists", chunks_table.table_id)

    documents_table = bigquery.Table(
        _table_ref(DOCUMENTS_TABLE), schema=_documents_schema()
    )
    documents_table = client.create_table(documents_table, exists_ok=True)
    logger.info("Ensured table %s exists", documents_table.table_id)


def insert_chunks(chunks: list[dict], doc_id: str) -> int:
    """Insert chunk rows into budget_chunks, tagging each with doc_id.

    Returns the number of rows successfully submitted to the streaming buffer.
    Raises RuntimeError if BigQuery reports any row-level errors.
    """
    if not chunks:
        return 0

    rows: list[dict[str, Any]] = []
    for i, chunk in enumerate(chunks):
        if "chunk_id" not in chunk or chunk["chunk_id"] is None:
            raise ValueError(f"chunk at index {i} is missing required key 'chunk_id'")
        if "embedding" not in chunk or chunk["embedding"] is None:
            raise ValueError(f"chunk at index {i} is missing required key 'embedding'")

        rows.append(
            {
                "chunk_id": chunk["chunk_id"],
                "page_number": chunk.get("page_number"),
                "section": chunk.get("section"),
                "ward": chunk.get("ward"),
                "text": chunk.get("text"),
                "doc_id": doc_id,
                "embedding": list(chunk["embedding"]),
            }
        )

    client = _client()
    table_ref = _table_ref(CHUNKS_TABLE)
    errors = client.insert_rows_json(table_ref, rows)
    if errors:
        logger.error("BigQuery insert_rows_json reported errors: %s", errors)
        raise RuntimeError(f"Failed to insert chunks into {table_ref}: {errors}")

    logger.info("Inserted %d chunks into %s (doc_id=%s)", len(rows), table_ref, doc_id)
    return len(rows)


def register_document(doc_id: str, source_url: str, version: str) -> None:
    """Insert a single provenance row into budget_documents."""
    client = _client()
    table_ref = _table_ref(DOCUMENTS_TABLE)
    rows = [
        {
            "doc_id": doc_id,
            "source_url": source_url,
            "version": version,
        }
    ]
    errors = client.insert_rows_json(table_ref, rows)
    if errors:
        logger.error("BigQuery insert_rows_json reported errors: %s", errors)
        raise RuntimeError(f"Failed to register document {doc_id}: {errors}")
    logger.info("Registered document %s (version=%s)", doc_id, version)


def vector_search(
    query_embedding: list[float],
    top_k: int = 8,
    ward: str | None = None,
) -> list[dict]:
    """Run a cosine VECTOR_SEARCH against budget_chunks.embedding.

    If `ward` is provided, the base table is narrowed with a CTE so the
    VECTOR_SEARCH TVF only scans matching rows. All inputs are bound as
    query parameters; no user string is interpolated into SQL.
    """
    client = _client()
    table_ref = _table_ref(CHUNKS_TABLE)

    # We always wrap the base table in a CTE: when ward is given we filter
    # there, otherwise we pass it through unchanged. Keeping one query shape
    # makes the param list stable and the plan easy to read.
    if ward is not None:
        base_cte = f"""
            SELECT *
            FROM `{table_ref}`
            WHERE ward = @ward
        """
    else:
        base_cte = f"""
            SELECT *
            FROM `{table_ref}`
        """

    sql = f"""
        WITH base AS (
            {base_cte}
        )
        SELECT
            base.chunk_id      AS chunk_id,
            base.page_number   AS page_number,
            base.section       AS section,
            base.ward          AS ward,
            base.text          AS text,
            distance           AS distance
        FROM VECTOR_SEARCH(
            TABLE base,
            'embedding',
            (SELECT @query_embedding AS embedding),
            top_k => @top_k,
            distance_type => 'COSINE'
        )
        ORDER BY distance ASC
    """

    params: list[bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter] = [
        bigquery.ArrayQueryParameter(
            "query_embedding", "FLOAT64", list(query_embedding)
        ),
        bigquery.ScalarQueryParameter("top_k", "INT64", int(top_k)),
    ]
    if ward is not None:
        params.append(bigquery.ScalarQueryParameter("ward", "STRING", ward))

    job_config = bigquery.QueryJobConfig(query_parameters=params)
    logger.debug(
        "Running VECTOR_SEARCH top_k=%d ward=%s on %s", top_k, ward, table_ref
    )
    rows = client.query(sql, job_config=job_config).result()

    results: list[dict] = []
    for row in rows:
        results.append(
            {
                "chunk_id": row["chunk_id"],
                "page_number": row["page_number"],
                "section": row["section"],
                "ward": row["ward"],
                "text": row["text"],
                "distance": row["distance"],
            }
        )
    return results
