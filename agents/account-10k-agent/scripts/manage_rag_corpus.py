#!/usr/bin/env python3
"""Manage Vertex AI RAG Corpus lifecycle and synchronize local .env configuration."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def parse_env_file(env_path: Path) -> dict[str, str]:
    """Parses key-value pairs from an existing .env file."""
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            values[key.strip()] = val.strip()
    return values


def update_env_file(env_path: Path, updates: dict[str, str]) -> None:
    """Updates key-value pairs in a .env file, preserving other lines and comments."""
    existing_lines: list[str] = []
    if env_path.is_file():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    updated_keys = set()
    new_lines: list[str] = []

    for line in existing_lines:
        trimmed = line.strip()
        if trimmed and not trimmed.startswith("#") and "=" in trimmed:
            key, _ = trimmed.split("=", 1)
            key = key.strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    for key, val in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"✅ Updated {env_path} successfully with: {list(updates.keys())}")


def get_vertex_client(project: str, location: str):
    """Initializes vertexai and imports rag module."""
    try:
        import vertexai
        from vertexai.preview import rag

        vertexai.init(project=project, location=location)
        return rag
    except ImportError:
        print("❌ Error: google-cloud-aiplatform is not installed. Run `uv sync` first.", file=sys.stderr)
        sys.exit(1)


def cmd_create(args: argparse.Namespace) -> None:
    """Provisions or looks up a Vertex AI RAG Corpus and prints its metadata."""
    rag = get_vertex_client(args.project, args.location)
    display_name = args.display_name

    try:
        corpora = list(rag.list_corpora())
        for corpus in corpora:
            if corpus.display_name == display_name:
                corpus_id = corpus.name.split("/")[-1]
                print(json.dumps({
                    "status": "existing",
                    "corpus_id": corpus_id,
                    "corpus_name": corpus.name,
                    "display_name": corpus.display_name,
                }))
                return
    except Exception as e:
        print(f"⚠️ Warning while listing corpora: {e}", file=sys.stderr)

    print(f"Creating Vertex AI RAG Corpus '{display_name}' with {args.embedding_model}...", file=sys.stderr)
    try:
        embedding_model_config = rag.EmbeddingModelConfig(
            publisher_model=args.embedding_model
        )
        corpus = rag.create_corpus(
            display_name=display_name,
            description="SEC 10-K Account Intelligence RAG corpus on Vertex AI",
            embedding_model_config=embedding_model_config,
        )
        corpus_id = corpus.name.split("/")[-1]
        print(json.dumps({
            "status": "created",
            "corpus_id": corpus_id,
            "corpus_name": corpus.name,
            "display_name": corpus.display_name,
        }))
    except Exception as e:
        err_msg = str(e).lower()
        if "unprovisioned" in err_msg or "serverless" in err_msg or "failedprecondition" in err_msg:
            print(f"⚠️ Detected unprovisioned Spanner RAG state. Automatically switching projects/{args.project}/locations/{args.location} to Serverless mode...", file=sys.stderr)
            cmd_switch_serverless(args)
            print("🔄 Retrying corpus creation in Serverless mode...", file=sys.stderr)
            try:
                corpus = rag.create_corpus(
                    display_name=display_name,
                    description="SEC 10-K Account Intelligence RAG corpus on Vertex AI",
                    embedding_model_config=rag.EmbeddingModelConfig(
                        publisher_model=args.embedding_model
                    ),
                )
                corpus_id = corpus.name.split("/")[-1]
                print(json.dumps({
                    "status": "created",
                    "corpus_id": corpus_id,
                    "corpus_name": corpus.name,
                    "display_name": corpus.display_name,
                }))
                return
            except Exception as retry_err:
                print(f"❌ Retry after switching to Serverless failed: {retry_err}", file=sys.stderr)
                sys.exit(1)

        print(f"❌ Failed to create RAG corpus: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_switch_serverless(args: argparse.Namespace) -> None:
    """Switches project RagEngineConfig to Serverless mode to resolve unprovisioned Spanner state."""
    project = args.project
    location = args.location
    print(f"🔄 Switching RAG Engine in projects/{project}/locations/{location} to Serverless mode...")

    # Attempt 1: Via Vertex AI Python SDK
    try:
        import vertexai
        from vertexai.preview import rag

        vertexai.init(project=project, location=location)
        config_name = f"projects/{project}/locations/{location}/ragEngineConfig"
        if hasattr(rag, "Serverless") and hasattr(rag, "RagManagedDbConfig"):
            new_config = rag.RagEngineConfig(
                name=config_name,
                rag_managed_db_config=rag.RagManagedDbConfig(mode=rag.Serverless()),
            )
            rag.rag_data.update_rag_engine_config(rag_engine_config=new_config)
            print("✅ Successfully switched to Serverless mode via Vertex AI SDK!")
            return
    except Exception as e:
        print(f"⚠️ SDK update attempt returned: {e}. Trying REST API fallback...", file=sys.stderr)

    # Attempt 2: Via Google Cloud REST API with ADC
    try:
        import json
        import urllib.request
        import google.auth
        import google.auth.transport.requests

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)

        url = f"https://{location}-aiplatform.googleapis.com/v1beta1/projects/{project}/locations/{location}/ragEngineConfig"
        payload = json.dumps({"ragManagedDbConfig": {"serverless": {}}}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json",
            },
            method="PATCH",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"✅ Successfully switched to Serverless mode via REST API: {data}")
            return
    except Exception as e:
        print(f"❌ Failed to switch to Serverless mode: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_get_config(args: argparse.Namespace) -> None:
    """Retrieves and prints the active RagEngineConfig for project/location."""
    project = args.project
    location = args.location
    try:
        import json
        import urllib.request
        import google.auth
        import google.auth.transport.requests

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)

        url = f"https://{location}-aiplatform.googleapis.com/v1beta1/projects/{project}/locations/{location}/ragEngineConfig"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json",
            },
            method="GET",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(json.dumps(data, indent=2))
            return
    except Exception as e:
        print(f"❌ Failed to fetch RagEngineConfig: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_switch_spanner_basic(args: argparse.Namespace) -> None:
    """Updates RagEngineConfig to Spanner Basic tier (100 processing units)."""
    project = args.project
    location = args.location
    print(f"🔄 Setting Spanner Basic tier in projects/{project}/locations/{location}...")
    # Attempt 1: Via Vertex AI Python SDK
    try:
        import vertexai
        from vertexai.preview import rag

        vertexai.init(project=project, location=location)
        config_name = f"projects/{project}/locations/{location}/ragEngineConfig"
        if hasattr(rag, "Spanner") and hasattr(rag, "Basic"):
            new_config = rag.RagEngineConfig(
                name=config_name,
                rag_managed_db_config=rag.RagManagedDbConfig(
                    mode=rag.Spanner(tier=rag.Basic())
                ),
            )
            rag.rag_data.update_rag_engine_config(rag_engine_config=new_config)
            print("✅ Successfully updated to Spanner Basic tier via Vertex AI SDK!")
            return
    except Exception as e:
        print(f"⚠️ SDK update attempt returned: {e}. Trying REST API fallback...", file=sys.stderr)

    # Attempt 2: Via REST API with ADC
    try:
        import json
        import urllib.request
        import google.auth
        import google.auth.transport.requests

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)

        url = f"https://{location}-aiplatform.googleapis.com/v1beta1/projects/{project}/locations/{location}/ragEngineConfig"
        payload = json.dumps({"ragManagedDbConfig": {"spanner": {"basic": {}}}}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json",
            },
            method="PATCH",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"✅ Successfully updated to Spanner Basic tier: {data}")
            return
    except Exception as e:
        print(f"❌ Failed to set Spanner Basic tier: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_delete(args: argparse.Namespace) -> None:
    """Deletes a Vertex AI RAG Corpus by ID or display name."""
    rag = get_vertex_client(args.project, args.location)

    target_name: str | None = None
    if args.corpus_id:
        target_name = f"projects/{args.project}/locations/{args.location}/ragCorpora/{args.corpus_id}"
    elif args.display_name:
        try:
            corpora = list(rag.list_corpora())
            for c in corpora:
                if c.display_name == args.display_name:
                    target_name = c.name
                    break
        except Exception as e:
            print(f"⚠️ Error listing corpora: {e}", file=sys.stderr)

    if not target_name:
        print(f"ℹ️ Corpus not found or already deleted (display_name={args.display_name}, id={args.corpus_id}).")
        return

    try:
        rag.delete_corpus(target_name)
        print(json.dumps({"status": "deleted", "corpus_name": target_name}))
    except Exception as e:
        print(f"❌ Error deleting corpus: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_status(args: argparse.Namespace) -> None:
    """Checks the status of the RAG corpus in Vertex AI."""
    rag = get_vertex_client(args.project, args.location)
    try:
        corpora = list(rag.list_corpora())
        found = [
            c for c in corpora
            if c.display_name == args.display_name or (args.corpus_id and args.corpus_id in c.name)
        ]
        if found:
            corpus = found[0]
            corpus_id = corpus.name.split("/")[-1]
            try:
                files = list(rag.list_files(corpus.name))
                file_count = len(files)
            except Exception:
                file_count = 0

            print(json.dumps({
                "status": "active",
                "corpus_id": corpus_id,
                "corpus_name": corpus.name,
                "display_name": corpus.display_name,
                "indexed_files_count": file_count,
            }, indent=2))
        else:
            print(json.dumps({
                "status": "not_found",
                "display_name": args.display_name,
                "corpus_id": args.corpus_id,
            }, indent=2))
    except Exception as e:
        print(f"❌ Failed to query status: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_sync_env(args: argparse.Namespace) -> None:
    """Updates local .env file with provisioned resources."""
    env_path = Path(args.env_path).resolve()
    updates: dict[str, str] = {}

    if args.project:
        updates["GOOGLE_CLOUD_PROJECT"] = args.project
    if args.location:
        updates["GOOGLE_CLOUD_LOCATION"] = args.location
    if args.rag_location:
        updates["RAG_LOCATION"] = args.rag_location
    if args.bucket:
        updates["GCS_DOCUMENTS_BUCKET"] = args.bucket
    if args.corpus_id is not None:
        updates["RAG_CORPUS_ID"] = args.corpus_id
    if args.display_name:
        updates["RAG_CORPUS_DISPLAY_NAME"] = args.display_name

    update_env_file(env_path, updates)


def main() -> None:
    parser = argparse.ArgumentParser(description="Vertex AI RAG Corpus and .env Lifecycle Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    default_rag_location = os.getenv("RAG_LOCATION") or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    p_create = subparsers.add_parser("create", help="Create or fetch Vertex AI RAG Corpus")
    p_create.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT", "mongo-experiments"))
    p_create.add_argument("--location", default=default_rag_location)
    p_create.add_argument("--display-name", default="account-10k-corpus")
    p_create.add_argument("--embedding-model", default="publishers/google/models/text-embedding-005")
    p_create.set_defaults(func=cmd_create)

    p_switch = subparsers.add_parser("switch-serverless", help="Switch project RAG Engine to Serverless mode")
    p_switch.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT", "mongo-experiments"))
    p_switch.add_argument("--location", default=default_rag_location)
    p_switch.set_defaults(func=cmd_switch_serverless)

    p_spanner = subparsers.add_parser("switch-spanner-basic", help="Set project RAG Engine to Spanner Basic tier")
    p_spanner.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT", "mongo-experiments"))
    p_spanner.add_argument("--location", default=default_rag_location)
    p_spanner.set_defaults(func=cmd_switch_spanner_basic)

    p_cfg = subparsers.add_parser("get-config", help="Get active RagEngineConfig for project/location")
    p_cfg.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT", "mongo-experiments"))
    p_cfg.add_argument("--location", default=default_rag_location)
    p_cfg.set_defaults(func=cmd_get_config)


    p_del = subparsers.add_parser("delete", help="Delete Vertex AI RAG Corpus")
    p_del.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT", "mongo-experiments"))
    p_del.add_argument("--location", default=default_rag_location)
    p_del.add_argument("--corpus-id", default="")
    p_del.add_argument("--display-name", default="account-10k-corpus")
    p_del.set_defaults(func=cmd_delete)

    p_status = subparsers.add_parser("status", help="Get status of Vertex AI RAG Corpus")
    p_status.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT", "mongo-experiments"))
    p_status.add_argument("--location", default=default_rag_location)
    p_status.add_argument("--corpus-id", default="")
    p_status.add_argument("--display-name", default="account-10k-corpus")
    p_status.set_defaults(func=cmd_status)

    p_sync = subparsers.add_parser("sync-env", help="Sync values to .env file")
    p_sync.add_argument("--env-path", default=".env")
    p_sync.add_argument("--project", default="")
    p_sync.add_argument("--location", default="")
    p_sync.add_argument("--rag-location", default="")
    p_sync.add_argument("--bucket", default="")
    p_sync.add_argument("--corpus-id", default=None)
    p_sync.add_argument("--display-name", default="")
    p_sync.set_defaults(func=cmd_sync_env)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

