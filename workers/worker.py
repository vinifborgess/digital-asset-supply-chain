"""
Our golem.

Continuously polls Postgres for assets with status = 'pending', decides where
each asset belongs based on its type, moves it in MinIO from incoming/ to
classified/<type>/, and updates its status to 'classified'.

This is the automated logistics agent: NO HUMAN decides where files go.
"""

import os
import time

import boto3
import psycopg2
from botocore.client import Config

# --- Configuration (from environment) ---
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "talos")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "change_me")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "talos_catalog")
POSTGRES_USER = os.getenv("POSTGRES_USER", "talos")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "change_me")

POLL_INTERVAL_SECONDS = 2
BATCH_SIZE = 5


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
    )


def get_pg_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )


def fetch_pending_batch(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, bucket, object_key, asset_type, name
            FROM assets
            WHERE status = 'pending'
            ORDER BY created_at
            LIMIT %s
            """,
            (BATCH_SIZE,),
        )
        return cur.fetchall()


def classify_asset(s3_client, bucket, object_key, asset_type, name):
    """Moves the object from incoming/... to classified/<type>/... """
    new_key = f"classified/{asset_type}/{name}"
    s3_client.copy_object(Bucket=bucket, CopySource={"Bucket": bucket, "Key": object_key}, Key=new_key)
    s3_client.delete_object(Bucket=bucket, Key=object_key)
    return new_key


def mark_classified(pg_conn, asset_id, new_key):
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            UPDATE assets
            SET status = 'classified', object_key = %s, updated_at = now()
            WHERE id = %s
            """,
            (new_key, asset_id),
        )
    pg_conn.commit()


def mark_error(pg_conn, asset_id):
    with pg_conn.cursor() as cur:
        cur.execute(
            "UPDATE assets SET status = 'error', updated_at = now() WHERE id = %s",
            (asset_id,),
        )
    pg_conn.commit()


def main():
    s3_client = get_s3_client()
    pg_conn = get_pg_connection()

    print("[golem] watching for pending assets. Ctrl+C to stop.")
    try:
        while True:
            batch = fetch_pending_batch(pg_conn)

            if not batch:
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            for asset_id, bucket, object_key, asset_type, name in batch:
                try:
                    new_key = classify_asset(s3_client, bucket, object_key, asset_type, name)
                    mark_classified(pg_conn, asset_id, new_key)
                    print(f"[classified] {name} ({asset_type}) -> {new_key}")
                except Exception as exc:
                    mark_error(pg_conn, asset_id)
                    print(f"[error] failed to classify {name}: {exc}")

            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\n[golem] stopped.")
    finally:
        pg_conn.close()


if __name__ == "__main__":
    main()