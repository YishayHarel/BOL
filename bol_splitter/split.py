"""Group scanned pages into documents and validate page completeness."""

from dataclasses import dataclass, field

from .parse import PageFields


@dataclass
class DocumentGroup:
    page_indices: list[int]  # 0-based indices into the source PDF
    pages: list[PageFields]
    warnings: list[str] = field(default_factory=list)

    @property
    def first(self) -> PageFields:
        return self.pages[0]


def group_pages(page_fields: list[PageFields]) -> list[DocumentGroup]:
    """Split the batch into documents using the printed "PAGE 1 OF N" marker.

    A new document starts on any page whose page_current == 1. Pages where the
    page number could not be read attach to the current document (safer than
    starting a spurious new one). The handwritten D# is intentionally ignored:
    it repeats across unrelated documents and is often missing entirely.
    """
    groups: list[DocumentGroup] = []
    for idx, page in enumerate(page_fields):
        starts_new = not groups or page.page_current == 1
        if starts_new:
            groups.append(DocumentGroup(page_indices=[idx], pages=[page]))
        else:
            groups[-1].page_indices.append(idx)
            groups[-1].pages.append(page)
    return groups


def validate_group(group: DocumentGroup) -> list[str]:
    warnings: list[str] = []

    totals = {p.page_total for p in group.pages if p.page_total is not None}
    if not totals:
        warnings.append("could not read 'PAGE X OF Y' on any page")
    elif len(totals) > 1:
        warnings.append(f"inconsistent page totals across pages: {sorted(totals)}")
    else:
        expected_total = next(iter(totals))
        seen = [p.page_current for p in group.pages]
        expected = list(range(1, expected_total + 1))
        if seen != expected:
            warnings.append(
                f"page sequence gap or disorder: read {seen}, expected {expected} "
                f"(likely a missing or misordered scanned page)"
            )

    for i, page in enumerate(group.pages):
        is_last = i == len(group.pages) - 1
        if is_last and page.more_pages_attached:
            warnings.append(
                "last page still shows 'MORE PAGE(S) ATTACHED' — document may be incomplete"
            )

    if group.first.date is None:
        warnings.append("date unreadable on first page")

    return warnings


def build_groups(page_fields: list[PageFields]) -> list[DocumentGroup]:
    groups = group_pages(page_fields)
    for group in groups:
        group.warnings = validate_group(group)
    return groups
