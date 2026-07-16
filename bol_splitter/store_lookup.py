"""Resolve a BOL Ship-To name to a folder bucket, using the store dump.

Strategy: (1) a direct keyword rule on the OCR'd text catches the common case
(the retailer name appears literally, e.g. "MARSHALLS DC-881"); (2) if not, fuzzy
-match against the store dump (rapidfuzz) so an odd store name or a slightly
misread name still lands on the right retailer; (3) otherwise OTHER.
"""

import json
import os

from rapidfuzz import fuzz, process

from .buckets import OTHER, bucket_for


class StoreMatcher:
    def __init__(self, index_path: str | None = None, threshold: int = 90):
        self.threshold = threshold
        self.names: list[str] = []
        self.buckets: list[str] = []
        if index_path and os.path.exists(index_path):
            with open(index_path) as f:
                data = json.load(f)
            self.names = data.get("names", [])
            self.buckets = data.get("buckets", [])

    def resolve(self, ship_to: str | None, fallback_text: str | None = None) -> str:
        """`ship_to` = the extracted Ship-To name (preferred); `fallback_text` =
        the whole page header text, used for the keyword pass when Ship-To
        extraction failed."""
        query = (ship_to or "").strip()

        # 1) direct keyword rule (fast, no fuzzy) on ship-to then whole header
        for text in (query, fallback_text or ""):
            b = bucket_for(text)
            if b != OTHER:
                return b

        # 2) fuzzy match the ship-to name against the dump
        if query and self.names:
            match = process.extractOne(
                query.upper(), self.names, scorer=fuzz.WRatio, score_cutoff=self.threshold
            )
            if match is not None:
                return self.buckets[match[2]]

        return OTHER
