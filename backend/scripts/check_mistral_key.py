#!/usr/bin/env python3
"""Verify MISTRAL_API_KEY is valid and mistral-ocr-2512 model is accessible.

Requires:
  - MISTRAL_API_KEY environment variable set
  - backend/tests/fixtures/one_page_test.pdf committed to the repo

Exits non-zero on any failure.
"""
from __future__ import annotations

import base64
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.join(SCRIPT_DIR, "..")
sys.path.insert(0, BACKEND_ROOT)

from app.agents.mistral_ocr_client import MISTRAL_OCR_MODEL, DocumentClassification


FIXTURE_PATH = os.path.join(BACKEND_ROOT, "tests", "fixtures", "one_page_test.pdf")


def main() -> None:
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        print("ERROR: MISTRAL_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    from mistralai.client import Mistral

    client = Mistral(api_key=api_key)

    # Step 1: Verify the pinned model is listed
    print(f"Checking that {MISTRAL_OCR_MODEL} is available...")
    models_response = client.models.list()
    model_ids = [m.id for m in models_response.data]
    if MISTRAL_OCR_MODEL not in model_ids:
        print(
            f"ERROR: {MISTRAL_OCR_MODEL} not found in available models.\n"
            f"Available: {model_ids}",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"  OK: {MISTRAL_OCR_MODEL} found in model list")

    # Step 2: OCR the fixture PDF
    if not os.path.isfile(FIXTURE_PATH):
        print(
            f"ERROR: Fixture not found at {FIXTURE_PATH}\n"
            "Please commit a 1-page test PDF to backend/tests/fixtures/one_page_test.pdf",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(FIXTURE_PATH, "rb") as f:
        pdf_bytes = f.read()

    print(f"Running OCR on fixture ({len(pdf_bytes)} bytes)...")
    encoded = base64.b64encode(pdf_bytes).decode("ascii")
    response = client.ocr.process(
        model=MISTRAL_OCR_MODEL,
        document={
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{encoded}",
        },
        include_image_base64=False,
    )
    print(f"  OK: OCR returned {len(response.pages)} page(s)")
    if response.usage_info:
        print(f"  Usage: {response.usage_info}")

    # Step 3: Verify document_annotation round-trips through DocumentClassification
    from mistralai.extra import response_format_from_pydantic_model

    response_with_annotation = client.ocr.process(
        model=MISTRAL_OCR_MODEL,
        document={
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{encoded}",
        },
        document_annotation_format=response_format_from_pydantic_model(
            DocumentClassification,
        ),
        include_image_base64=False,
    )

    raw_annotation = response_with_annotation.document_annotation
    if raw_annotation is None:
        print("ERROR: document_annotation is null", file=sys.stderr)
        sys.exit(1)
    print(f"  OK: document_annotation is non-null")

    if isinstance(raw_annotation, str):
        parsed = json.loads(raw_annotation)
    else:
        parsed = raw_annotation

    classification = DocumentClassification.model_validate(parsed)
    if not classification.document_type:
        print("ERROR: classification.document_type is empty", file=sys.stderr)
        sys.exit(1)
    print(f"  OK: classification.document_type = {classification.document_type}")
    print(f"  OK: confidence = {classification.confidence}")
    print(f"  OK: reasoning = {classification.reasoning[:100]}...")

    print()
    print("Health check passed.")


if __name__ == "__main__":
    main()
