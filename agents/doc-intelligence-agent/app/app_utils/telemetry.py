"""Configure GenAI prompt/response logging and OpenTelemetry."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def setup_telemetry() -> str | None:
    """Configures GenAI prompt/response logging via OpenTelemetry."""
    os.environ.setdefault("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", "false")

    bucket = os.environ.get("LOGS_BUCKET_NAME")
    capture_content = os.environ.get(
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "false"
    )
    if bucket and capture_content != "false":
        logger.info(
            "Prompt-response logging enabled - mode: NO_CONTENT"
        )
        os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "NO_CONTENT"
        os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_UPLOAD_FORMAT", "jsonl")
        os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK", "upload")
        os.environ.setdefault(
            "OTEL_SEMCONV_STABILITY_OPT_IN", "gen_ai_latest_experimental"
        )
        commit_sha = os.environ.get("COMMIT_SHA", "dev")
        os.environ.setdefault(
            "OTEL_RESOURCE_ATTRIBUTES",
            f"service.namespace=doc-intelligence-agent,service.version={commit_sha}",
        )
        path = os.environ.get("GENAI_TELEMETRY_PATH", "completions")
        os.environ.setdefault(
            "OTEL_INSTRUMENTATION_GENAI_UPLOAD_BASE_PATH",
            f"gs://{bucket}/{path}",
        )

    try:
        import google.auth
        from google.adk.cli.api_server import _setup_instrumentation_lib_if_installed
        from google.adk.telemetry.google_cloud import get_gcp_exporters, get_gcp_resource
        from google.adk.telemetry.setup import maybe_set_otel_providers

        credentials, project_id = google.auth.default()
        otel_hooks = get_gcp_exporters(
            enable_cloud_tracing=True,
            enable_cloud_metrics=False,
            enable_cloud_logging=True,
            google_auth=(credentials, project_id),
        )
        otel_resource = get_gcp_resource(project_id)
        maybe_set_otel_providers(
            otel_hooks_to_setup=[otel_hooks],
            otel_resource=otel_resource,
        )
        _setup_instrumentation_lib_if_installed()
    except Exception as e:
        logger.debug("Telemetry setup skipped or partial: %s", e)

    return bucket

