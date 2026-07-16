"""Map a customer/store name to one of the fixed folder buckets, or OTHER.

The 10 buckets get their own folders; everyone else is filed under OTHER.
Marmaxx covers the whole TJX/Marmaxx family (TJ Maxx, Marshalls, HomeGoods,
Sierra), which is how these BOLs' ship-to names appear.
"""

OTHER = "OTHER"

BUCKETS = [
    "Target", "Walmart", "Marmaxx", "Ross", "Burlington",
    "Amazon", "CVS", "Academy", "DSG", "Meijer",
]

# (bucket, keywords) — checked in order; first keyword hit wins.
_RULES = [
    ("Marmaxx", ["MARMAXX", "MARSHALL", "TJ MAXX", "T.J.MAXX", "TJMAXX",
                 "HOMEGOOD", "HOME GOODS", "SIERRA TRADING"]),
    ("Walmart", ["WAL-MART", "WALMART", "WAL MART"]),
    ("Target", ["TARGET"]),
    ("Burlington", ["BURLINGTON", "BURLINGT"]),
    ("Amazon", ["AMAZON"]),
    ("Academy", ["ACADEMY"]),
    ("Meijer", ["MEIJER"]),
    ("DSG", ["DICK'S", "DICKS", "DICK S SPORTING", "DICK SPORTING", "DSG"]),
    ("CVS", ["CVS"]),
    ("Ross", ["ROSS"]),
]

COMPANY_ABBREV = {
    "FitForLife": "FFL",
    "Supply Accessories": "SA",
    "Capture Accessories": "CA",
}


def bucket_for(name: str) -> str:
    if not name:
        return OTHER
    upper = name.upper()
    for bucket, keywords in _RULES:
        if any(kw in upper for kw in keywords):
            return bucket
    return OTHER


def company_abbrev(company: str) -> str:
    return COMPANY_ABBREV.get(company, "UnknownCo")
