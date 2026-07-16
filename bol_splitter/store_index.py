"""Build a compact store->bucket lookup from the Customer & Store Dump Report.

Run once (build step). Reads the ~500k-row dump and writes a small JSON mapping
every retailer store/customer NAME to its folder bucket. Only rows that resolve
to one of the 10 buckets are kept; everyone else is OTHER by default at runtime,
so the file stays small. openpyxl is only needed here, never at runtime.
"""

import json

import openpyxl

from .buckets import OTHER, bucket_for

# Sheet2 columns (0-based): C=2 Customer#, E=4 Customer Name, G=6 Store Name 1
COL_CUSTOMER_NAME = 4
COL_STORE_NAME = 6


def build_index(xlsx_path: str, out_path: str, sheet: str = "Sheet2") -> int:
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb[sheet]

    mapping: dict[str, str] = {}  # NAME (upper) -> bucket
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < 3:  # skip header rows
            continue
        customer_name = str(row[COL_CUSTOMER_NAME] or "").strip()
        store_name = str(row[COL_STORE_NAME] or "").strip()

        bucket = bucket_for(customer_name)
        if bucket == OTHER:
            bucket = bucket_for(store_name)
        if bucket == OTHER:
            continue  # not one of the 10 retailers — leave it to default OTHER

        for name in (customer_name, store_name):
            if name:
                mapping[name.upper()] = bucket

    names = list(mapping.keys())
    payload = {"names": names, "buckets": [mapping[n] for n in names]}
    with open(out_path, "w") as f:
        json.dump(payload, f)
    wb.close()
    return len(names)


if __name__ == "__main__":
    import sys

    count = build_index(sys.argv[1], sys.argv[2])
    print(f"wrote {count} name->bucket entries to {sys.argv[2]}")
