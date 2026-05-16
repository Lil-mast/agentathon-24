from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from google.cloud import bigquery


def _client() -> bigquery.Client:
    return bigquery.Client()


def _table(config: dict, table_name: str) -> str:
    return f"{config['GOOGLE_CLOUD_PROJECT']}.{config['BQ_DATASET']}.{table_name}"


def ensure_person3_tables(config: dict) -> None:
    client = _client()
    dataset_id = f"{config['GOOGLE_CLOUD_PROJECT']}.{config['BQ_DATASET']}"
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


def upsert_subscriber(config: dict, row: dict[str, Any], unsubscribe_only: bool = False) -> None:
    client = _client()
    table_id = _table(config, "subscribers")
    now = datetime.now(timezone.utc).isoformat()

    if unsubscribe_only:
        query = f"""
        UPDATE `{table_id}`
        SET active = FALSE
        WHERE phone = @phone
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("phone", "STRING", row["phone"])]
        )
        client.query(query, job_config=job_config).result()
        return

    query = f"""
    MERGE `{table_id}` T
    USING (
      SELECT @phone AS phone, @ward AS ward, @language AS language, TIMESTAMP(@subscribed_at) AS subscribed_at, @active AS active
    ) S
    ON T.phone = S.phone
    WHEN MATCHED THEN
      UPDATE SET ward = S.ward, language = S.language, subscribed_at = S.subscribed_at, active = TRUE
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


def list_active_subscribers(config: dict) -> list[dict[str, Any]]:
    client = _client()
    query = f"""
    SELECT phone, ward, language
    FROM `{_table(config, 'subscribers')}`
    WHERE active = TRUE
    """
    rows = client.query(query).result()
    return [dict(r.items()) for r in rows]


def get_subscriber(config: dict, phone: str) -> dict[str, Any] | None:
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


def insert_notices(config: dict, notices: list[dict[str, Any]]) -> int:
    if not notices:
        return 0
    client = _client()

    existing_hashes = set(_existing_notice_hashes(config, [n["hash"] for n in notices]))
    fresh = [n for n in notices if n["hash"] not in existing_hashes]
    if not fresh:
        return 0

    errors = client.insert_rows_json(_table(config, "gazette_notices"), fresh)
    if errors:
        raise RuntimeError(f"insert_notices failed: {errors}")
    return len(fresh)


def _existing_notice_hashes(config: dict, hashes: list[str]) -> list[str]:
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


def list_unprocessed_notices(config: dict, limit: int = 50) -> list[dict[str, Any]]:
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


def mark_notice_processed(config: dict, notice_id: str) -> None:
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


def insert_amendment(config: dict, amendment: dict[str, Any]) -> None:
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
      SELECT @amendment_id AS amendment_id, @notice_id AS notice_id, @ward AS ward, @sector AS sector,
             @change_summary AS change_summary, @amount_delta AS amount_delta, TIMESTAMP(@detected_at) AS detected_at
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


def list_amendments(config: dict, ward: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
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


def list_recent_amendments_for_ward(config: dict, ward: str, days: int = 7) -> list[dict[str, Any]]:
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


def list_top_allocations_for_ward(config: dict, ward: str, top_k: int = 3) -> list[dict[str, Any]]:
    # Expected to be replaced with Person 1 table query once schema is finalized.
    client = _client()
    table_id = _table(config, "budget_chunks")
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


def log_sms(config: dict, phone: str, message: str, status: str) -> None:
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
