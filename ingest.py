"""
Simulates producers (players/designers) continuously generating digital assets.

Each cycle:
    1. Generates a synthetic asset (random type, name, size)
    2. Uploads it to MinIO
    3. Inserts its metadata into Postgres with status = 'pending'

Run this as a long-lived process. It loops indefinitely with a randomized
interval between uploads, so the pipeline can be observed live end to end.

"""

import io
import os
import random
import time
import uuid

import boto3
import psycopg2
from botocore.client import Config

# --- Configuration (from environment) ---
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "talos")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "change_me")
BUCKET_NAME = os.getenv("MINIO_BUCKET", "talos-raw")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "talos_catalog")
POSTGRES_USER = os.getenv("POSTGRES_USER", "talos")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "change_me")

ASSET_TYPES = ["image", "video", "document", "model_3d", "audio"]
PROJECTS = ["brand-campaign", "product-launch", "internal-training", "client-alpha", "client-beta"]

MIN_INTERVAL_SECONDS = 3
MAX_INTERVAL_SECONDS = 8


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


def ensure_bucket(s3_client):
    existing = [b["Name"] for b in s3_client.list_buckets().get("Buckets", [])]
    if BUCKET_NAME not in existing:
        s3_client.create_bucket(Bucket=BUCKET_NAME)
        print(f"[setup] created bucket '{BUCKET_NAME}'")


def generate_synthetic_asset():
    asset_type = random.choice(ASSET_TYPES)
    project = random.choice(PROJECTS)
    asset_id = str(uuid.uuid4())
    name = f"{asset_type}_{asset_id[:8]}"
    size_bytes = random.randint(10_000, 5_000_000)
    content = os.urandom(min(size_bytes, 65536))  # cap actual payload for speed; size_bytes is the recorded metadata
    return {
        "id": asset_id,
        "name": name,
        "asset_type": asset_type,
        "origin_project": project,
        "size_bytes": size_bytes,
        "content": content,
    }


def upload_asset(s3_client, asset):
    object_key = f"incoming/{asset['origin_project']}/{asset['name']}"
    s3_client.upload_fileobj(io.BytesIO(asset["content"]), BUCKET_NAME, object_key)
    return object_key


def insert_metadata(pg_conn, asset, object_key):
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO assets (id, name, asset_type, origin_project, bucket, object_key, size_bytes, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
            """,
            (
                asset["id"],
                asset["name"],
                asset["asset_type"],
                asset["origin_project"],
                BUCKET_NAME,
                object_key,
                asset["size_bytes"],
            ),
        )
    pg_conn.commit()


def main():
    s3_client = get_s3_client()
    ensure_bucket(s3_client)
    pg_conn = get_pg_connection()

    print("[ingestion] starting continuous asset generation. Ctrl+C to stop.")
    try:
        while True:
            asset = generate_synthetic_asset()
            object_key = upload_asset(s3_client, asset)
            insert_metadata(pg_conn, asset, object_key)

            print(
                f"[ingested] {asset['name']} "
                f"(type={asset['asset_type']}, project={asset['origin_project']}, "
                f"size={asset['size_bytes']} bytes) -> {object_key}"
            )

            time.sleep(random.uniform(MIN_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS))
    except KeyboardInterrupt:
        print("\n[ingestion] stopped.")
    finally:
        pg_conn.close()


if __name__ == "__main__":
    main()
