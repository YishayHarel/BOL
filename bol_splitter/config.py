"""Load the candidate name list Joseph provides (companies + customers)."""

import json
import os
from dataclasses import dataclass


@dataclass
class Candidates:
    companies: list[str]
    customers: list[str]
    fuzzy_threshold: int = 80


def load_candidates(path: str) -> Candidates:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Candidate list not found: {path}. "
            f"Copy candidates.example.json to candidates.json and edit it."
        )
    with open(path) as f:
        data = json.load(f)
    return Candidates(
        companies=data.get("companies", []),
        customers=data.get("customers", []),
        fuzzy_threshold=int(data.get("fuzzy_threshold", 80)),
    )
