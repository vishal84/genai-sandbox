"""Google Cloud Storage Signed URL Generation.

Generates short-lived, secure V4 signed URLs for GCS PDF documents so analysts
can instantly download or view original source documents directly from citations.
"""

from __future__ import annotations

import datetime
import logging
import os
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def parse_gcs_uri(gcs_uri: str) -> tuple[str, str]:
    """Parses a gs://bucket/path/to/blob URI into (bucket_name, blob_name)."""
    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"Invalid GCS URI format: {gcs_uri}. Must start with 'gs://'")
    parsed = urlparse(gcs_uri)
    bucket_name = parsed.netloc
    blob_name = parsed.path.lstrip("/")
    return bucket_name, blob_name


def generate_gcs_signed_url(
    gcs_uri: str,
    expiration_minutes: int | None = None,
) -> str:
    """Generates a V4 signed URL for a given GCS object URI.

    Args:
        gcs_uri: A Cloud Storage URI (e.g. gs://my-bucket/docs/report.pdf)
        expiration_minutes: Expiration duration in minutes (default from ENV or 60m).

    Returns:
        The HTTPS signed URL, or fallback public/console link if signing is unavailable.
    """
    if not gcs_uri or not gcs_uri.startswith("gs://"):
        return gcs_uri

    if expiration_minutes is None:
        expiration_minutes = int(os.getenv("SIGNED_URL_EXPIRATION_MINUTES", "60"))

    try:
        bucket_name, blob_name = parse_gcs_uri(gcs_uri)
        from google.cloud import storage

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=expiration_minutes),
            method="GET",
        )
        return signed_url

    except Exception as e:
        logger.warning(
            "Could not generate signed URL for %s (%s). Generating Cloud Console fallback link.",
            gcs_uri,
            e,
        )
        # Fallback to Google Cloud Storage web console URL
        try:
            b_name, b_path = parse_gcs_uri(gcs_uri)
            return f"https://console.cloud.google.com/storage/browser/_details/{b_name}/{b_path}"
        except Exception:
            return gcs_uri

