"""
Post-session synthesis.

After an interactive review session produces N per-page reports, this
module generates two additional artefacts:

  1. A **combined report** — deterministic concatenation of all per-page
     reports with clear page separators. No LLM, no rewriting.

  2. A **prioritised synthesis** — a single ranked list of cross-page
     issues with explicit page references. For LLM modes, Claude reads
     all per-page reports and produces a grounded priority list; the
     prompt forbids inventing findings not present in the source. For
     no-LLM modes, a deterministic aggregator counts issue types and
     ranks by frequency.

The per-page reports are never modified. Users keep all original detail;
the synthesis just helps them see the forest for the trees.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass


SYNTHESIS_PROMPT_TEMPLATE = """\
You are synthesising design-review findings across {n} pages of an app.

IMPORTANT RULES (your output will be rejected if you violate any):
1. Do NOT invent findings. Every priority you list MUST correspond to a
   finding that appears in the per-page reports below.
2. Every priority MUST cite the page index (e.g. "Page 2") where the
   finding came from. If a finding appears on multiple pages, cite them
   all.
3. Do NOT rewrite per-page findings. Reference them briefly, then state
   why this priority matters across pages.
4. Rank priorities by: severity first (things that block users), then
   frequency (issues that appear on multiple pages), then effort-to-fix
   (low-effort high-impact wins first).
5. Maximum 10 priorities. Quality over quantity.

---

PER-PAGE REPORTS:

{reports}

---

Produce output in this exact format:

# Prioritised Synthesis — {n} pages reviewed

## Top Priorities

1. **[Severity] Short title** — which pages: Page X, Page Y
   One-sentence statement of the cross-cutting issue. Why it's a priority.
   Fix direction (one sentence).

2. **[Severity] Short title** — which pages: Page X
   ...

## Patterns I noticed

- Patterns that recur across 3+ pages (bullet list, one line each)

## Single-page issues worth flagging

- Items that only appear on one page but are severe enough to ship fixes for
"""


@dataclass
class CaptureRef:
    """Lightweight view of a capture for synthesis."""
    index: int
    url: str
    report_markdown: str
    label: str = ""  # human-readable page label (e.g. "Dashboard")

    @property
    def display_name(self) -> str:
        if self.label:
            return f"{self.label}"
        return self.url


# ── Deterministic combined report ──


def build_combined_report(captures: list[CaptureRef], session_mode: str) -> str:
    """Concatenate per-page reports with clear separators. No LLM, no rewrite."""
    if not captures:
        return "# Interactive session\n\n_No pages captured._"

    lines = [
        f"# Interactive Review — {len(captures)} page(s)",
        "",
        f"**Mode:** {session_mode}",
        "",
        "## Table of Contents",
        "",
    ]
    for c in captures:
        anchor = f"page-{c.index}"
        heading = f"{c.label or 'Page ' + str(c.index)}"
        lines.append(f"{c.index}. [{heading}](#{anchor}) — {c.url}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for c in captures:
        anchor = f"page-{c.index}"
        heading = c.label or f"Page {c.index}"
        lines.append(f"<a id='{anchor}'></a>")
        lines.append("")
        lines.append(f"# Page {c.index}: {heading}")
        lines.append(f"_{c.url}_")
        lines.append("")
        lines.append(c.report_markdown.strip())
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ── Deterministic priority synthesis (for no-LLM audits) ──


def _extract_element_mentions(report_body: str) -> list[tuple[str, str]]:
    """Find (criterion, element-selector) pairs mentioned in a per-page report.

    Pattern: `**criterion**` followed by a list of bullets with `` `element` ``.
    Returns a list of (criterion, element) pairs for that page.
    """
    pairs: list[tuple[str, str]] = []
    # Split the body by criterion sections.
    # A criterion section starts with `**<crit>** violations` or similar bold.
    sections = re.split(r"\*\*(\d+\.\d+\.\d+[^*]*)\*\*", report_body)
    # Pattern produces [prefix, crit1, body1, crit2, body2, ...]
    for i in range(1, len(sections) - 1, 2):
        criterion = sections[i].strip().rstrip(":").strip()
        body = sections[i + 1]
        # Pull out bullet items mentioning elements in backticks
        for match in re.finditer(r"- `([^`]+)`", body):
            element = match.group(1).strip()
            pairs.append((criterion, element))
    return pairs


def _build_quick_wins(
    issue_pages: dict[str, list[int]],
    element_pages: dict[tuple[str, str], list[int]],
    total_pages: int,
    label_by_index: dict[int, str],
) -> list[str]:
    """Identify the handful of fixes that resolve the most violations.

    A quick win is either:
      - a criterion appearing on 50%+ of pages (fix the system, not 13 pages)
      - a specific element appearing on 3+ pages with the same violation
    """
    wins: list[str] = []

    # System-wide issues (50%+ of pages)
    threshold = max(2, total_pages // 2)
    for criterion, pages in sorted(
        issue_pages.items(), key=lambda kv: -len(kv[1])
    ):
        if len(pages) >= threshold and len(pages) > 1:
            wins.append(
                f"**{criterion}** appears on **{len(pages)} of {total_pages} pages**. "
                f"Likely a system-wide issue (shared token, shared component). "
                f"Fix once to resolve {len(pages)} pages."
            )

    # Specific elements recurring
    for (crit, elem), pages in sorted(
        element_pages.items(), key=lambda kv: -len(kv[1])
    ):
        if len(pages) >= 3:
            wins.append(
                f"`{elem}` fails **{crit}** on {len(pages)} pages. "
                f"Shared component — fix once to resolve {len(pages)} failures."
            )

    return wins[:5]


def build_priorities_deterministic(captures: list[CaptureRef]) -> str:
    """Rank issue types by frequency across pages. No LLM."""
    if not captures:
        return "# Prioritised Synthesis\n\n_No pages captured._"

    # Very coarse: count occurrences of WCAG criteria names in the combined
    # reports. Works because our pragmatic WCAG rendering always emits the
    # criterion name in a predictable format.
    criterion_pattern = re.compile(
        r"\*\*(\d+\.\d+\.\d+[^*]*)\*\*", re.MULTILINE,
    )
    issue_pages: dict[str, list[int]] = {}
    element_pages: dict[tuple[str, str], list[int]] = {}
    for c in captures:
        found = criterion_pattern.findall(c.report_markdown)
        seen_on_this_page: set[str] = set()
        for criterion in found:
            key = criterion.strip().rstrip(":").strip()
            if not key or key in seen_on_this_page:
                continue
            seen_on_this_page.add(key)
            issue_pages.setdefault(key, []).append(c.index)

        # Per-element pair extraction for cross-page dedup
        seen_pairs: set[tuple[str, str]] = set()
        for pair in _extract_element_mentions(c.report_markdown):
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            element_pages.setdefault(pair, []).append(c.index)

    if not issue_pages:
        return (
            "# Prioritised Synthesis\n\n"
            "_No structured WCAG issues detected across captures._"
        )

    # Rank by frequency, break ties alphabetically.
    ranked = sorted(
        issue_pages.items(),
        key=lambda kv: (-len(kv[1]), kv[0]),
    )

    # Build a page-index → label map so the output names pages usefully.
    label_by_index = {c.index: (c.label or f"Page {c.index}") for c in captures}

    lines = [
        f"# Prioritised Synthesis — {len(captures)} page(s) reviewed",
        "",
    ]

    # Quick wins section first (highest-ROI fixes)
    quick_wins = _build_quick_wins(
        issue_pages, element_pages, len(captures), label_by_index,
    )
    if quick_wins:
        lines.append("## Quick wins — fix these first")
        lines.append("")
        lines.append("_High-ROI fixes: each one resolves multiple pages/elements at once._")
        lines.append("")
        for win in quick_wins:
            lines.append(f"- {win}")
        lines.append("")

    # Cross-page element dedup: same element failing on N pages
    recurring_elements = sorted(
        [
            (crit, elem, pages)
            for (crit, elem), pages in element_pages.items()
            if len(pages) >= 2
        ],
        key=lambda t: (-len(t[2]), t[0], t[1]),
    )
    if recurring_elements:
        lines.append("## Elements failing across multiple pages")
        lines.append("")
        lines.append("_Likely shared components — fix once, resolve everywhere._")
        lines.append("")
        for crit, elem, pages in recurring_elements[:15]:
            page_names = ", ".join(
                label_by_index.get(p, f"Page {p}") for p in pages[:6]
            )
            more = f" … +{len(pages) - 6} more" if len(pages) > 6 else ""
            lines.append(
                f"- `{elem}` — **{crit}** — {len(pages)} pages "
                f"({page_names}{more})"
            )
        lines.append("")

    lines.append("## All issues ranked by how often they appear")
    lines.append("")
    for criterion, pages in ranked[:20]:
        page_list = ", ".join(label_by_index.get(p, f"Page {p}") for p in pages)
        multiplier = f" ({len(pages)} pages)" if len(pages) > 1 else ""
        lines.append(f"- **{criterion}**{multiplier} — {page_list}")
    lines.append("")

    # Scoring methodology footer (feedback item #7)
    lines.append("---")
    lines.append("")
    lines.append("## Scoring methodology")
    lines.append("")
    lines.append(
        "WCAG scores are calculated from A/AA failures only (AAA criteria "
        "are aspirational and excluded). Per-page WCAG score = "
        "`passing_criteria / testable_criteria × 100`. A fix that resolves "
        "one criterion on one page moves that page's score by ~10pp "
        "(there are 10 testable A/AA criteria)."
    )
    lines.append("")
    lines.append("_Full findings for each page remain in the per-page reports._")
    return "\n".join(lines)


# ── LLM-driven priority synthesis ──


def build_priorities_llm(captures: list[CaptureRef], provider=None) -> str:
    """Ask the LLM to produce a grounded priority list.

    `provider` is a callable `(prompt: str) -> str` — injected for testing.
    If None, falls back to the project's default critique LLM wiring.
    """
    if not captures:
        return "# Prioritised Synthesis\n\n_No pages captured._"

    formatted_reports = []
    for c in captures:
        heading = c.label or c.url
        formatted_reports.append(
            f"### Page {c.index} — {heading}\n_{c.url}_\n\n{c.report_markdown.strip()}"
        )
    prompt = SYNTHESIS_PROMPT_TEMPLATE.format(
        n=len(captures),
        reports="\n\n".join(formatted_reports),
    )

    if provider is None:
        provider = _default_llm_provider

    try:
        return provider(prompt)
    except Exception as exc:
        # Fall back to deterministic view if the LLM fails.
        return (
            f"# Prioritised Synthesis — LLM call failed\n\n"
            f"_Could not reach the LLM for synthesis: {exc}_\n\n"
            "Showing deterministic priority list as fallback:\n\n"
            + build_priorities_deterministic(captures)
        )


def _default_llm_provider(prompt: str) -> str:
    """Default LLM provider — uses the project's configured model."""
    from src.providers.llm import call_llm
    return call_llm(
        system_prompt="You are synthesising design findings across multiple pages.",
        user_prompt=prompt,
        max_tokens=2048,
    )


# ── Top-level synthesiser dispatch ──


def synthesise_session(
    captures: list[CaptureRef],
    session_mode: str,
    llm_provider=None,
) -> tuple[str, str]:
    """Return (combined_report, priorities) for a finished session.

    For pragmatic-audit mode → deterministic priorities only (no LLM call).
    For pragmatic-critique / deep-critique → LLM-driven priorities with
    deterministic fallback on failure.
    """
    combined = build_combined_report(captures, session_mode)
    if session_mode == "pragmatic-audit":
        priorities = build_priorities_deterministic(captures)
    else:
        priorities = build_priorities_llm(captures, provider=llm_provider)
    return combined, priorities
