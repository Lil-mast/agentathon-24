"""BigQuery helpers.

This module unifies two concerns:

* Person 1 (ingest + vector search): `ensure_dataset_and_tables`,
  `insert_chunks`, `register_document`, `vector_search`.
* Person 2 (subscribers + gazette + amendments + sms_log):
  `ensure_person3_tables`, `upsert_subscriber`, `list_active_subscribers`,
  `get_subscriber`, `insert_notices`, `list_unprocessed_notices`,
  `mark_notice_processed`, `insert_amendment`, `list_amendments`,
  `list_recent_amendments_for_ward`, `list_top_allocations_for_ward`,
  `log_sms`.

A single process-wide BigQuery client is shared between both subsystems.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any

from google.cloud import bigquery

from app.config import Config

logger = logging.getLogger(__name__)

_BQ_CLIENT: bigquery.Client | None = None

CHUNKS_TABLE = "budget_chunks"
DOCUMENTS_TABLE = "budget_documents"


def _client() -> bigquery.Client:
    """Process-wide BigQuery client, built lazily."""
    global _BQ_CLIENT
    if _BQ_CLIENT is None:
        logger.debug(
            "Constructing BigQuery client (project=%s, location=%s)",
            Config.GCP_PROJECT_ID,
            Config.BQ_LOCATION,
        )
        _BQ_CLIENT = bigquery.Client(
            project=Config.GCP_PROJECT_ID or None,
            location=Config.BQ_LOCATION,
        )
    return _BQ_CLIENT


def _dataset_ref() -> str:
    return f"{Config.GCP_PROJECT_ID}.{Config.BQ_DATASET}"


def _table_ref(table_name: str) -> str:
    return f"{_dataset_ref()}.{table_name}"


def _table(config: Any, table_name: str) -> str:
    """Config-dict variant used by Person 2 helpers.

    Falls back to Config-class attributes if the dict is missing keys.
    """
    if isinstance(config, dict):
        project = (
            config.get("GCP_PROJECT_ID")
            or config.get("GOOGLE_CLOUD_PROJECT")
            or Config.GCP_PROJECT_ID
        )
        dataset = config.get("BQ_DATASET", Config.BQ_DATASET)
    else:
        project = (
            getattr(config, "GCP_PROJECT_ID", "")
            or getattr(config, "GOOGLE_CLOUD_PROJECT", "")
            or Config.GCP_PROJECT_ID
        )
        dataset = getattr(config, "BQ_DATASET", Config.BQ_DATASET)
    return f"{project}.{dataset}.{table_name}"


# ---------------------------------------------------------------------------
# Person 1: ingest + vector search
# ---------------------------------------------------------------------------


def _chunks_schema() -> list[bigquery.SchemaField]:
    return [
        bigquery.SchemaField("chunk_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("page_number", "INT64", mode="NULLABLE"),
        bigquery.SchemaField("section", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("ward", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("text", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("doc_id", "STRING", mode="NULLABLE"),
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
    """Create the budget dataset + budget_chunks + budget_documents tables."""
    client = _client()

    dataset = bigquery.Dataset(_dataset_ref())
    dataset.location = Config.BQ_LOCATION
    dataset = client.create_dataset(dataset, exists_ok=True)
    logger.info("Ensured dataset %s exists in %s", dataset.dataset_id, dataset.location)

    chunks_table = bigquery.Table(_table_ref(CHUNKS_TABLE), schema=_chunks_schema())
    chunks_table = client.create_table(chunks_table, exists_ok=True)
    logger.info("Ensured table %s exists", chunks_table.table_id)

    documents_table = bigquery.Table(_table_ref(DOCUMENTS_TABLE), schema=_documents_schema())
    documents_table = client.create_table(documents_table, exists_ok=True)
    logger.info("Ensured table %s exists", documents_table.table_id)


def insert_chunks(chunks: list[dict], doc_id: str) -> int:
    """Insert chunks for `doc_id`, replacing any existing rows for that doc_id."""
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

    delete_job = client.query(
        f"DELETE FROM `{table_ref}` WHERE doc_id = @doc_id",
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("doc_id", "STRING", doc_id)]
        ),
    )
    delete_job.result()
    logger.info(
        "Cleared %s existing chunks for doc_id=%s",
        delete_job.num_dml_affected_rows or 0,
        doc_id,
    )

    buf = io.BytesIO()
    for row in rows:
        buf.write((json.dumps(row) + "\n").encode("utf-8"))
    buf.seek(0)

    load_job = client.load_table_from_file(
        buf,
        table_ref,
        job_config=bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        ),
    )
    load_job.result()
    logger.info("Inserted %d chunks into %s (doc_id=%s)", len(rows), table_ref, doc_id)
    return len(rows)


def register_document(doc_id: str, source_url: str, version: str) -> None:
    """Idempotent upsert of a row in budget_documents keyed by doc_id."""
    client = _client()
    table_ref = _table_ref(DOCUMENTS_TABLE)
    sql = f"""
        MERGE `{table_ref}` T
        USING (SELECT @doc_id AS doc_id) S
        ON T.doc_id = S.doc_id
        WHEN MATCHED THEN
            UPDATE SET
                source_url = @source_url,
                ingested_at = CURRENT_TIMESTAMP(),
                version = @version
        WHEN NOT MATCHED THEN
            INSERT (doc_id, source_url, ingested_at, version)
            VALUES (@doc_id, @source_url, CURRENT_TIMESTAMP(), @version)
    """
    job = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("doc_id", "STRING", doc_id),
                bigquery.ScalarQueryParameter("source_url", "STRING", source_url),
                bigquery.ScalarQueryParameter("version", "STRING", version),
            ]
        ),
    )
    job.result()
    logger.info("Registered document %s (version=%s)", doc_id, version)


def vector_search(
    query_embedding: list[float],
    top_k: int = 8,
    ward: str | None = None,
) -> list[dict]:
    """Cosine VECTOR_SEARCH against budget_chunks.embedding."""
    client = _client()
    table_ref = _table_ref(CHUNKS_TABLE)

    if ward is not None:
        table_arg = f"(SELECT * FROM `{table_ref}` WHERE ward = @ward)"
    else:
        table_arg = f"TABLE `{table_ref}`"

    sql = f"""
        SELECT
            base.chunk_id      AS chunk_id,
            base.page_number   AS page_number,
            base.section       AS section,
            base.ward          AS ward,
            base.text          AS text,
            distance           AS distance
        FROM VECTOR_SEARCH(
            {table_arg},
            'embedding',
            (SELECT @query_embedding AS embedding),
            top_k => @top_k,
            distance_type => 'COSINE'
        )
        ORDER BY distance ASC
    """

    params: list[bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter] = [
        bigquery.ArrayQueryParameter("query_embedding", "FLOAT64", list(query_embedding)),
        bigquery.ScalarQueryParameter("top_k", "INT64", int(top_k)),
    ]
    if ward is not None:
        params.append(bigquery.ScalarQueryParameter("ward", "STRING", ward))

    job_config = bigquery.QueryJobConfig(query_parameters=params)
    logger.debug("Running VECTOR_SEARCH top_k=%d ward=%s on %s", top_k, ward, table_ref)
    rows = client.query(sql, job_config=job_config).result()

    return [
        {
            "chunk_id": row["chunk_id"],
            "page_number": row["page_number"],
            "section": row["section"],
            "ward": row["ward"],
            "text": row["text"],
            "distance": row["distance"],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Person 2: subscribers / gazette / amendments / sms log
# ---------------------------------------------------------------------------


def ensure_person3_tables(config: Any) -> None:
    client = _client()
    if isinstance(config, dict):
        project = config.get("GCP_PROJECT_ID") or config.get("GOOGLE_CLOUD_PROJECT") or Config.GCP_PROJECT_ID
        dataset = config.get("BQ_DATASET", Config.BQ_DATASET)
    else:
        project = getattr(config, "GCP_PROJECT_ID", "") or getattr(config, "GOOGLE_CLOUD_PROJECT", "") or Config.GCP_PROJECT_ID
        dataset = getattr(config, "BQ_DATASET", Config.BQ_DATASET)

    dataset_id = f"{project}.{dataset}"
    client.create_dataset(bigquery.Dataset(dataset_id), exists_ok=True)

    table_specs = {
        "subscribers": [
            bigquery.SchemaField("phone", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("ward", "STRING"),
            bigquery.SchemaField("language", "STRING"),
            bigquery.SchemaField("subscribed_at", "TIMESTAMP"),
            bigquery.SchemaField("active", "BOOL"),
        ],
        "gazette_notices": [
            bigquery.SchemaField("notice_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("published_at", "TIMESTAMP"),
            bigquery.SchemaField("title", "STRING"),
            bigquery.SchemaField("url", "STRING"),
            bigquery.SchemaField("raw_text", "STRING"),
            bigquery.SchemaField("hash", "STRING"),
            bigquery.SchemaField("processed", "BOOL"),
        ],
        "budget_amendments": [
            bigquery.SchemaField("amendment_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("notice_id", "STRING"),
            bigquery.SchemaField("ward", "STRING"),
            bigquery.SchemaField("sector", "STRING"),
            bigquery.SchemaField("change_summary", "STRING"),
            bigquery.SchemaField("amount_delta", "FLOAT64"),
            bigquery.SchemaField("detected_at", "TIMESTAMP"),
        ],
        "sms_log": [
            bigquery.SchemaField("phone", "STRING"),
            bigquery.SchemaField("message", "STRING"),
            bigquery.SchemaField("status", "STRING"),
            bigquery.SchemaField("sent_at", "TIMESTAMP"),
        ],
    }

    for table_name, schema in table_specs.items():
        table_id = _table(config, table_name)
        table = bigquery.Table(table_id, schema=schema)
        client.create_table(table, exists_ok=True)


def upsert_subscriber(config: Any, row: dict[str, Any], unsubscribe_only: bool = False) -> None:
    client = _client()
    table_id = _table(config, "subscribers")
    now = datetime.now(timezone.utc).isoformat()

    if unsubscribe_only:
        query = f"UPDATE `{table_id}` SET active = FALSE WHERE phone = @phone"
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("phone", "STRING", row["phone"])]
        )
        client.query(query, job_config=job_config).result()
        return

    query = f"""
    MERGE `{table_id}` T
    USING (
      SELECT @phone AS phone, @ward AS ward, @language AS language,
             TIMESTAMP(@subscribed_at) AS subscribed_at, @active AS active
    ) S
    ON T.phone = S.phone
    WHEN MATCHED THEN
      UPDATE SET ward = S.ward, language = S.language,
                 subscribed_at = S.subscribed_at, active = TRUE
    WHEN NOT MATCHED THEN
      INSERT (phone, ward, language, subscribed_at, active)
      VALUES (S.phone, S.ward, S.language, S.subscribed_at, S.active)
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("phone", "STRING", row["phone"]),
            bigquery.ScalarQueryParameter("ward", "STRING", row["ward"]),
            bigquery.ScalarQueryParameter("language", "STRING", row["language"]),
            bigquery.ScalarQueryParameter("subscribed_at", "STRING", row.get("subscribed_at", now)),
            bigquery.ScalarQueryParameter("active", "BOOL", True),
        ]
    )
    client.query(query, job_config=job_config).result()


def list_active_subscribers(config: Any) -> list[dict[str, Any]]:
    client = _client()
    query = f"""
    SELECT phone, ward, language
    FROM `{_table(config, 'subscribers')}`
    WHERE active = TRUE
    """
    rows = client.query(query).result()
    return [dict(r.items()) for r in rows]


def get_subscriber(config: Any, phone: str) -> dict[str, Any] | None:
    client = _client()
    query = f"""
    SELECT phone, ward, language, active
    FROM `{_table(config, 'subscribers')}`
    WHERE phone = @phone
    LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("phone", "STRING", phone)]
    )
    rows = list(client.query(query, job_config=job_config).result())
    return dict(rows[0].items()) if rows else None


def insert_notices(config: Any, notices: list[dict[str, Any]]) -> int:
    if not notices:
        return 0
    client = _client()

    existing = set(_existing_notice_hashes(config, [n["hash"] for n in notices]))
    fresh = [n for n in notices if n["hash"] not in existing]
    if not fresh:
        return 0

    errors = client.insert_rows_json(_table(config, "gazette_notices"), fresh)
    if errors:
        raise RuntimeError(f"insert_notices failed: {errors}")
    return len(fresh)


def _existing_notice_hashes(config: Any, hashes: list[str]) -> list[str]:
    if not hashes:
        return []
    client = _client()
    query = f"""
    SELECT hash
    FROM `{_table(config, 'gazette_notices')}`
    WHERE hash IN UNNEST(@hashes)
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ArrayQueryParameter("hashes", "STRING", hashes)]
    )
    rows = client.query(query, job_config=job_config).result()
    return [r["hash"] for r in rows]


def list_unprocessed_notices(config: Any, limit: int = 50) -> list[dict[str, Any]]:
    client = _client()
    query = f"""
    SELECT notice_id, title, raw_text, published_at
    FROM `{_table(config, 'gazette_notices')}`
    WHERE processed = FALSE
    ORDER BY published_at DESC
    LIMIT @limit
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("limit", "INT64", limit)]
    )
    rows = client.query(query, job_config=job_config).result()
    return [dict(r.items()) for r in rows]


def mark_notice_processed(config: Any, notice_id: str) -> None:
    client = _client()
    query = f"""
    UPDATE `{_table(config, 'gazette_notices')}`
    SET processed = TRUE
    WHERE notice_id = @notice_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("notice_id", "STRING", notice_id)]
    )
    client.query(query, job_config=job_config).result()


def insert_amendment(config: Any, amendment: dict[str, Any]) -> None:
    client = _client()
    amendment_id = hashlib.sha256(
        json.dumps(
            {
                "notice_id": amendment.get("notice_id", ""),
                "ward": amendment.get("ward", ""),
                "sector": amendment.get("sector", ""),
                "change_summary": amendment.get("change_summary", ""),
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    row = {
        "amendment_id": amendment_id,
        "notice_id": amendment.get("notice_id"),
        "ward": amendment.get("ward"),
        "sector": amendment.get("sector"),
        "change_summary": amendment.get("change_summary"),
        "amount_delta": amendment.get("amount_delta"),
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }

    query = f"""
    MERGE `{_table(config, 'budget_amendments')}` T
    USING (
      SELECT @amendment_id AS amendment_id, @notice_id AS notice_id, @ward AS ward,
             @sector AS sector, @change_summary AS change_summary,
             @amount_delta AS amount_delta, TIMESTAMP(@detected_at) AS detected_at
    ) S
    ON T.amendment_id = S.amendment_id
    WHEN NOT MATCHED THEN
      INSERT (amendment_id, notice_id, ward, sector, change_summary, amount_delta, detected_at)
      VALUES (S.amendment_id, S.notice_id, S.ward, S.sector, S.change_summary, S.amount_delta, S.detected_at)
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("amendment_id", "STRING", row["amendment_id"]),
            bigquery.ScalarQueryParameter("notice_id", "STRING", row["notice_id"]),
            bigquery.ScalarQueryParameter("ward", "STRING", row["ward"]),
            bigquery.ScalarQueryParameter("sector", "STRING", row["sector"]),
            bigquery.ScalarQueryParameter("change_summary", "STRING", row["change_summary"]),
            bigquery.ScalarQueryParameter("amount_delta", "FLOAT64", row["amount_delta"]),
            bigquery.ScalarQueryParameter("detected_at", "STRING", row["detected_at"]),
        ]
    )
    client.query(query, job_config=job_config).result()


def list_amendments(config: Any, ward: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    client = _client()
    where = "WHERE ward = @ward" if ward else ""
    query = f"""
    SELECT amendment_id, notice_id, ward, sector, change_summary, amount_delta, detected_at
    FROM `{_table(config, 'budget_amendments')}`
    {where}
    ORDER BY detected_at DESC
    LIMIT @limit
    """
    params = [bigquery.ScalarQueryParameter("limit", "INT64", limit)]
    if ward:
        params.append(bigquery.ScalarQueryParameter("ward", "STRING", ward))
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    rows = client.query(query, job_config=job_config).result()
    return [dict(r.items()) for r in rows]


def list_recent_amendments_for_ward(config: Any, ward: str, days: int = 7) -> list[dict[str, Any]]:
    client = _client()
    query = f"""
    SELECT ward, sector, change_summary, amount_delta, detected_at
    FROM `{_table(config, 'budget_amendments')}`
    WHERE ward = @ward
      AND detected_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
    ORDER BY detected_at DESC
    LIMIT 10
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("ward", "STRING", ward),
            bigquery.ScalarQueryParameter("days", "INT64", days),
        ]
    )
    rows = client.query(query, job_config=job_config).result()
    return [dict(r.items()) for r in rows]


def list_top_allocations_for_ward(config: Any, ward: str, top_k: int = 3) -> list[dict[str, Any]]:
    client = _client()
    table_id = _table(config, CHUNKS_TABLE)
    query = f"""
    SELECT section, text
    FROM `{table_id}`
    WHERE ward = @ward
    LIMIT @top_k
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("ward", "STRING", ward),
            bigquery.ScalarQueryParameter("top_k", "INT64", top_k),
        ]
    )
    rows = client.query(query, job_config=job_config).result()
    return [dict(r.items()) for r in rows]


def log_sms(config: Any, phone: str, message: str, status: str) -> None:
    client = _client()
    row = {
        "phone": phone,
        "message": message,
        "status": status,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    errors = client.insert_rows_json(_table(config, "sms_log"), [row])
    if errors:
        raise RuntimeError(f"log_sms failed: {errors}")
