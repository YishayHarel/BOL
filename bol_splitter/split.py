"""Group scanned pages into documents and validate completeness.

Boundary rule (confirmed with real consolidated loads):
- A new file starts on each page whose title is "BILL OF LADING" /
  "MASTER BILL OF LADING" AND which shows the SHIP FROM / SHIP TO blocks
  (i.e. a real BOL front page).
- "SUPPLEMENT" continuation pages, and any page without those header blocks,
  attach to the current file — so a multi-page BOL stays in one file.
- A "BOL Manifest Report" (a summary) attaches to the END of the file it follows,
  like a continuation page.

The "PAGE X OF Y" counter is not used as a boundary — on a consolidated load it
paginates the whole truckload, not the individual bills of lading.
"""

from dataclasses import dataclass, field

from .parse import DOC_BOL, DOC_MASTER, PageFields


@dataclass
class DocumentGroup:
    page_indices: list[int]  # 0-based indices into the source PDF
    pages: list[PageFields]
    warnings: list[str] = field(default_factory=list)

    @property
    def first(self) -> PageFields:
        return self.pages[0]


def group_pages(page_fields: list[PageFields]) -> list[DocumentGroup]:
    groups: list[DocumentGroup] = []
    current_bol: str | None = None

    for idx, page in enumerate(page_fields):
        # A new file starts only on a "(MASTER) BILL OF LADING" title page.
        # SUPPLEMENT / manifest / unreadable pages attach to the current file.
        is_header = page.doc_type in (DOC_BOL, DOC_MASTER)
        starts_new = not groups or is_header

        if starts_new:
            groups.append(DocumentGroup(page_indices=[idx], pages=[page]))
            current_bol = page.bol_number
        else:
            groups[-1].page_indices.append(idx)
            groups[-1].pages.append(page)
            if current_bol is None and page.bol_number is not None:
                current_bol = page.bol_number
    return groups


def load_sequence_warnings(page_fields: list[PageFields]) -> dict[int, str]:
    """Detect missing scanned pages: within a run of pages sharing the same
    "PAGE _ OF Y" total, the page numbers should increase by exactly 1.
    """
    warnings: dict[int, str] = {}
    for i in range(1, len(page_fields)):
        prev, cur = page_fields[i - 1], page_fields[i]
        if (
            prev.page_total is not None
            and cur.page_total is not None
            and prev.page_total == cur.page_total
            and prev.page_current is not None
            and cur.page_current is not None
            and cur.page_current > prev.page_current + 1
        ):
            missing = list(range(prev.page_current + 1, cur.page_current))
            warnings[i] = (
                f"missing scanned page(s) {missing} of {cur.page_total} "
                f"(page numbers jumped {prev.page_current} -> {cur.page_current})"
            )
    return warnings


def validate_group(group: DocumentGroup) -> list[str]:
    warnings: list[str] = []
    if group.first.doc_type not in (DOC_BOL, DOC_MASTER):
        warnings.append(
            "document does not start on a readable '(MASTER) BILL OF LADING' title page"
        )
    if group.first.date is None:
        warnings.append("date unreadable on first page")
    return warnings


def build_groups(page_fields: list[PageFields]) -> list[DocumentGroup]:
    groups = group_pages(page_fields)

    index_to_group = {idx: g for g in groups for idx in g.page_indices}
    for page_index, message in load_sequence_warnings(page_fields).items():
        group = index_to_group.get(page_index)  # skip warnings on dropped manifest pages
        if group is not None:
            group.warnings.append(message)

    for group in groups:
        group.warnings.extend(validate_group(group))
    return groups
