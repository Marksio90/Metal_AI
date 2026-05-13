from __future__ import annotations

import hashlib


def anonymize_text(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"anon_{digest}"


def anonymize_filename(filename: str) -> str:
    return anonymize_text(filename)
