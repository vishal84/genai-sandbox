#!/usr/bin/env python3
"""Manage Vertex AI RAG Corpus lifecycle and synchronize local .env configuration."""

from __future__ import annotations

import argparse
import json
import os
import re
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

    # Append any keys that didn't already exist in the file
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

    # Check existing corpora
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

    # Create new corpus
    print(f"Creating Vertex AI RAG Corpus '{display_name}' with {args.embedding_model}...", file=sys.stderr)
    try:
        embedding_model_config = rag.EmbeddingModelConfig(
            publisher_model=args.embedding_model
        )
        corpus = rag.create_corpus(
            display_name=display_name,
            description="Doc Intelligence RAG corpus provisioned via Terraform / automation",
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
        print(f"❌ Failed to create RAG corpus: {e}", file=sys.stderr)
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

    print(f"Deleting Vertex AI RAG Corpus '{target_name}'...", file=sys.stderr)
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
        found = [c for c in corpora if c.display_name == args.display_name or (args.corpus_id and args.corpus_id in c.name)]
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
    if args.corpus_id:
        updates["RAG_CORPUS_ID"] = args.corpus_id
    if args.display_name:
        updates["RAG_CORPUS_DISPLAY_NAME"] = args.display_name

    update_env_file(env_path, updates)


def main() -> None:
    parser = argparse.ArgumentParser(description="Vertex AI RAG Corpus and .env Lifecycle Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    default_rag_location = os.getenv("RAG_LOCATION") or os.getenv("GOOGLE_CLOUD_LOCATION", "us-east4")

    # Subcommand: create
    p_create = subparsers.add_parser("create", help="Create or fetch Vertex AI RAG Corpus")
    p_create.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT", "mongo-experiments"))
    p_create.add_argument("--location", default=default_rag_location)
    p_create.add_argument("--display-name", default="doc-intelligence-corpus")
    p_create.add_argument("--embedding-model", default="publishers/google/models/text-embedding-005")
    p_create.set_defaults(func=cmd_create)

    # Subcommand: delete
    p_del = subparsers.add_parser("delete", help="Delete Vertex AI RAG Corpus")
    p_del.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT", "mongo-experiments"))
    p_del.add_argument("--location", default=default_rag_location)
    p_del.add_argument("--corpus-id", default="")
    p_del.add_argument("--display-name", default="doc-intelligence-corpus")
    p_del.set_defaults(func=cmd_delete)

    # Subcommand: status
    p_status = subparsers.add_parser("status", help="Get status of Vertex AI RAG Corpus")
    p_status.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT", "mongo-experiments"))
    p_status.add_argument("--location", default=default_rag_location)
    p_status.add_argument("--corpus-id", default="")
    p_status.add_argument("--display-name", default="doc-intelligence-corpus")
    p_status.set_defaults(func=cmd_status)

    # Subcommand: sync-env
    p_sync = subparsers.add_parser("sync-env", help="Sync values to .env file")
    p_sync.add_argument("--env-path", default=".env")
    p_sync.add_argument("--project", default="")
    p_sync.add_argument("--location", default="")
    p_sync.add_argument("--rag-location", default="")
    p_sync.add_argument("--bucket", default="")
    p_sync.add_argument("--corpus-id", default="")
    p_sync.add_argument("--display-name", default="")
    p_sync.set_defaults(func=cmd_sync_env)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

