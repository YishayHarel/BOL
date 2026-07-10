"""Fuzzy-match messy OCR text against a clean candidate list (TheFuzz)."""

from dataclasses import dataclass
from typing import Optional

from thefuzz import fuzz


@dataclass
class MatchResult:
    canonical: Optional[str]  # the matched candidate, or None if below threshold
    score: int                # best fuzzy score found (0-100)


def match_name(text: str, candidates: list[str], threshold: int = 80) -> MatchResult:
    """Find the best candidate that appears anywhere in the OCR text.

    Uses partial_ratio so a short clean candidate ("WALMART") can match inside
    a longer noisy OCR block ("SHIP TO NAME: WAL-MART DC 6561A ..."). Returns
    the canonical candidate string when confident, else None for manual review.
    """
    text_upper = text.upper()
    best_name: Optional[str] = None
    best_score = 0
    for candidate in candidates:
        score = fuzz.partial_ratio(candidate.upper(), text_upper)
        if score > best_score:
            best_score = score
            best_name = candidate
    if best_score >= threshold:
        return MatchResult(canonical=best_name, score=best_score)
    return MatchResult(canonical=None, score=best_score)
