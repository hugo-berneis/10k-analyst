"""Pulls Item 1A (Risk Factors) and Item 7 (MD&A) out of a 10-K's HTML.

10-Ks don't mark these sections up in any structured way, so this relies on
a heuristic every EDGAR-parsing tool shares: read the document as a flat
sequence of leaf-level text blocks, then find each "Item N" heading by
matching lines that *start* with it. A bare "starts with Item N" match is
unreliable on its own because every 10-K repeats each heading several times:
once as a table-of-contents entry, once as the real section heading, and
(for some filers, Microsoft included) again as a running page header on
every page within the section.

What distinguishes the *real* heading pair from the noise isn't how the
heading itself is formatted -- some filers put the title in the same block
("Item 1A. Risk Factors"), others split it into a following block ("Item
1A." / "Risk Factors") -- it's what comes between one real heading and the
next: hundreds of paragraphs of body text. Table-of-contents and running-
header repeats of consecutive item labels, by contrast, sit only a few
blocks apart. So for each candidate "Item 1A" position, this pairs it with
the nearest following "Item 1B" (or "Item 1C", if a filer skips 1B in the
body -- Pfizer does) candidate and keeps whichever pair has the largest gap
between them.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# 10-K filings sometimes open with an XML declaration even though the body
# is HTML, which makes bs4 warn needlessly every time we parse one.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

BLOCK_TAGS = ("p", "div", "li", "td")

# A block shorter than this is almost always a page header/footer ("Apple
# Inc. | 2025 Form 10-K | 5") or a bare subheading, not risk/MD&A prose.
MIN_PARAGRAPH_CHARS = 40

_ITEM_1A = re.compile(r"^item\s+1a\b", re.IGNORECASE)
_ITEM_1B = re.compile(r"^item\s+1b\b", re.IGNORECASE)
_ITEM_1C = re.compile(r"^item\s+1c\b", re.IGNORECASE)
_ITEM_7 = re.compile(r"^item\s+7\b", re.IGNORECASE)
_ITEM_7A = re.compile(r"^item\s+7a\b", re.IGNORECASE)
_ITEM_8 = re.compile(r"^item\s+8\b", re.IGNORECASE)


@dataclass(frozen=True)
class Paragraph:
    paragraph_id: str
    ticker: str
    fiscal_year: int
    section: str
    index: int
    text: str

    @property
    def char_count(self) -> int:
        return len(self.text)


class SectionNotFoundError(Exception):
    """Raised when a 10-K doesn't have a heading this heuristic can find."""


def extract_leaf_blocks(html: str) -> list[str]:
    """Document text as an ordered list of leaf block-tag contents.

    A "leaf" is a `<p>`/`<div>`/`<li>`/`<td>` with no block-tag descendant of
    its own, which avoids double-counting text that nested divs would
    otherwise repeat.
    """
    soup = BeautifulSoup(html, "lxml")
    blocks = []
    for tag in soup.find_all(BLOCK_TAGS):
        if tag.find(BLOCK_TAGS) is not None:
            continue
        text = tag.get_text(" ", strip=True)
        if text:
            blocks.append(text)
    return blocks


def _match_indices(blocks: list[str], pattern: re.Pattern) -> list[int]:
    return [i for i, block in enumerate(blocks) if pattern.match(block)]


def _widest_gap_pair(starts: list[int], ends: list[int]) -> tuple[int, int] | None:
    """Pair each start with its nearest following end, keep the widest pair.

    The real section is the pair with the most body text between the two
    headings; table-of-contents and running-header repeats of the same
    labels sit only a few blocks apart.
    """
    best: tuple[int, int] | None = None
    for start in starts:
        following = [end for end in ends if end > start]
        if not following:
            continue
        end = min(following)
        if best is None or (end - start) > (best[1] - best[0]):
            best = (start, end)
    return best


# How many leading blocks after a heading label to check for a spilled-over
# title. Real prose is virtually never this short *and* unterminated more
# than once or twice in a row, so the bound keeps this from eating real
# content in sections that happen to open with a short paragraph.
_MAX_TITLE_FRAGMENTS = 2


def _drop_spilled_title(blocks: list[str]) -> list[str]:
    """Drop a heading's title when it landed in its own block, not the label's.

    Some filers put "Item 7." and its title ("Management's Discussion and
    Analysis...") in separate tags. Since a title is long enough to survive
    the paragraph-length filter but is a fragment, not a sentence, it never
    ends in terminal punctuation -- unlike real prose.
    """
    i = 0
    while (
        i < len(blocks)
        and i < _MAX_TITLE_FRAGMENTS
        and not blocks[i].rstrip().endswith((".", "!", "?", ":"))
    ):
        i += 1
    return blocks[i:]


def _slice_section(
    blocks: list[str],
    start_pattern: re.Pattern,
    end_patterns: list[re.Pattern],
    label: str,
) -> list[str]:
    starts = _match_indices(blocks, start_pattern)
    ends = sorted({i for pattern in end_patterns for i in _match_indices(blocks, pattern)})
    pair = _widest_gap_pair(starts, ends)
    if pair is None:
        raise SectionNotFoundError(f"Could not find a heading pair for {label}")
    start, end = pair
    return _drop_spilled_title(blocks[start + 1 : end])


def extract_paragraphs(html: str, ticker: str, fiscal_year: int) -> list[Paragraph]:
    """Split a 10-K's Item 1A and Item 7 sections into tagged paragraphs."""
    blocks = extract_leaf_blocks(html)
    sections = {
        "risk_factors": _slice_section(blocks, _ITEM_1A, [_ITEM_1B, _ITEM_1C], "Item 1A"),
        "mdna": _slice_section(blocks, _ITEM_7, [_ITEM_7A, _ITEM_8], "Item 7"),
    }

    paragraphs = []
    for section, raw_blocks in sections.items():
        index = 0
        for block in raw_blocks:
            text = block.strip()
            if len(text) < MIN_PARAGRAPH_CHARS:
                continue
            paragraphs.append(
                Paragraph(
                    paragraph_id=f"{ticker}-{fiscal_year}-{section}-{index}",
                    ticker=ticker,
                    fiscal_year=fiscal_year,
                    section=section,
                    index=index,
                    text=text,
                )
            )
            index += 1
    return paragraphs
