#!/usr/bin/env python3
"""Reprocess documents with low AI confidence scores using the preferred LLM."""

import argparse
import os
from pathlib import Path
from typing import List

from document_processor import DocumentProcessor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reprocess documents that have low AI confidence scores."
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.01,
        help="Maximum confidence score to target (default: 0.01)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of documents to reprocess (default: 100)",
    )
    parser.add_argument(
        "--llm",
        type=str,
        default=None,
        help="Override LLM provider (gemini|groq). Uses LLM_PROVIDER env if omitted.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only list candidate documents without reprocessing",
    )
    return parser.parse_args()


def load_candidates(processor: DocumentProcessor, threshold: float, limit: int) -> List[dict]:
    query = (
        processor.supabase
        .table("documents")
        .select("id,file_name,current_path,confidence_score,ai_category")
        .lte("confidence_score", threshold)
        .order("updated_at", desc=True)
        .limit(limit)
    )
    result = query.execute()
    return result.data or []


def main() -> None:
    args = parse_args()
    processor = DocumentProcessor(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        llm_provider=args.llm,
    )

    candidates = load_candidates(processor, args.threshold, args.limit)
    if not candidates:
        print("No documents found below confidence threshold.")
        return

    print(
        f"Found {len(candidates)} documents with confidence <= {args.threshold}."
    )

    if args.dry_run:
        for doc in candidates:
            print(
                f"[DRY-RUN] {doc['file_name']} | confidence={doc['confidence_score']:.3f}"
            )
        return

    processed = 0
    skipped = 0
    for doc in candidates:
        file_path = doc.get("current_path")
        if not file_path or not os.path.exists(file_path):
            print(
                f"⚠️  Skipping {doc['file_name']}: file not found at {file_path}"
            )
            skipped += 1
            continue

        print(
            f"\n==== Reprocessing {doc['file_name']} (confidence={doc['confidence_score']:.3f}) ===="
        )
        result = processor.process_document(file_path, skip_if_exists=False)
        if result.get("status") == "success":
            processed += 1
        else:
            skipped += 1

    print(
        f"\nReprocess complete. Updated {processed} document(s), skipped {skipped}."
    )


if __name__ == "__main__":
    main()
