"""
Structural page fingerprinting for SPA crawl deduplication.

When crawling an SPA, routes like /exercises/1, /exercises/2, ... often
share a single template. Text content differs but structure is identical.
Capturing all of them is wasteful and drowns real variety in the report.

The fingerprint ignores text content, attribute values, and styling — it
keys on the tree shape: which landmarks are present, what the heading
hierarchy looks like, and how interactive elements are grouped. Two pages
with the same fingerprint are the "same template" for review purposes.

Pure function — takes a DOM-data dict, returns a stable hash string.
"""

from __future__ import annotations

import hashlib
from collections import Counter


def structural_fingerprint(dom_data: dict) -> str:
    """Return a stable 16-char hash derived from page structure only.

    Inputs used (all from the DOM extractor's output):
      - landmarks present (main, nav, header, footer, aside)
      - heading level sequence (h1, h2, h2, h3, ...)
      - form input count
      - interactive element count (bucketed to avoid minor variance)
      - top-level font-size count (typography scale width)
    """
    html = dom_data.get("html_structure", {}) or {}

    # Landmark presence (sorted for stability)
    landmarks = html.get("landmarks", {}) or {}
    landmark_key = "|".join(
        f"{name}={1 if landmarks.get(name, 0) > 0 else 0}"
        for name in sorted(["main", "nav", "header", "footer", "aside"])
    )

    # Heading level sequence (e.g. "1-2-2-3-2-3")
    headings = html.get("headings", []) or []
    heading_key = "-".join(str(h.get("level", "")) for h in headings)

    # Form inputs
    forms = html.get("forms", {}) or {}
    input_count = (
        len(forms.get("inputs_without_labels", []))
        + len(forms.get("selects_without_labels", []))
    )
    # Also count properly-labelled inputs via interactive elements
    interactive = dom_data.get("interactive_elements", []) or []
    interactive_input_count = sum(
        1 for e in interactive
        if str(e.get("element", "")).startswith(("input", "select", "textarea"))
    )
    total_inputs = input_count + interactive_input_count

    # Bucket interactive-element count (5 buckets: 0, 1-5, 6-15, 16-40, 40+)
    interactive_total = len(interactive)
    if interactive_total == 0:
        interactive_bucket = "0"
    elif interactive_total <= 5:
        interactive_bucket = "1-5"
    elif interactive_total <= 15:
        interactive_bucket = "6-15"
    elif interactive_total <= 40:
        interactive_bucket = "16-40"
    else:
        interactive_bucket = "40+"

    # Interactive element type distribution (bucketed, text-free)
    def _bucket(n: int) -> str:
        if n == 0:
            return "0"
        if n <= 5:
            return "1-5"
        if n <= 15:
            return "6-15"
        if n <= 40:
            return "16-40"
        return "40+"

    tag_counts = Counter()
    for e in interactive:
        tag = str(e.get("element", "")).split(".")[0].split("#")[0]
        if tag:
            tag_counts[tag] += 1
    tag_key = "|".join(
        f"{t}={_bucket(c)}" for t, c in sorted(tag_counts.items())
    )

    # Typography scale width (number of distinct font sizes, bucketed)
    fonts = dom_data.get("fonts", {}) or {}
    size_count = len(fonts.get("sizes", []))

    # Compose the full key
    composite = "||".join([
        f"landmarks:{landmark_key}",
        f"headings:{heading_key}",
        f"inputs:{total_inputs}",
        f"interactive:{interactive_bucket}",
        f"tags:{tag_key}",
        f"typescale:{size_count}",
    ])

    return hashlib.sha256(composite.encode()).hexdigest()[:16]


def is_same_template(fp_a: str, fp_b: str) -> bool:
    """Alias for clarity — two fingerprints being equal means same template."""
    return fp_a == fp_b
