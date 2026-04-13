"""
Before/after diff analyser.

Compares two designs and produces a structured delta: score change, per-bucket
issue diff (fixed / new / persistent), and a visual PNG diff with changed
regions outlined. Inputs can be URLs, local images, or a URL + its stored
history baseline.

Reuses the CI runner's fingerprinting logic so "what counts as a violation"
stays consistent between the gate and the diff tool.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json

from PIL import Image, ImageChops, ImageDraw

from src.analysis.ci_runner import (
    ViolationFingerprint,
    _fingerprint_wcag_violations,
    _fingerprint_axe_violations,
)


SCHEMA_VERSION = 1

EXIT_PASS = 0
EXIT_THRESHOLD_FAILED = 1
EXIT_TECHNICAL_ERROR = 2

DEFAULT_SCORE_TOLERANCE = 2.0  # pp — matches pragmatic CI default


@dataclass
class IssueDiff:
    new: list[dict] = field(default_factory=list)
    fixed: list[dict] = field(default_factory=list)
    persistent: list[dict] = field(default_factory=list)


@dataclass
class DiffReport:
    schema_version: int
    before_label: str
    after_label: str
    score_before: float | None
    score_after: float | None
    score_delta: float | None
    issues: IssueDiff
    visual_diff_path: str | None
    visual_diff_regions: int
    exit_code: int
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "before_label": self.before_label,
            "after_label": self.after_label,
            "score_before": self.score_before,
            "score_after": self.score_after,
            "score_delta": self.score_delta,
            "new_issues": self.issues.new,
            "fixed_issues": self.issues.fixed,
            "persistent_issues": self.issues.persistent,
            "visual_diff_path": self.visual_diff_path,
            "visual_diff_regions": self.visual_diff_regions,
            "exit_code": self.exit_code,
            "errors": self.errors,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Before / After Diff",
            "",
            f"**Before:** {self.before_label}",
            f"**After:** {self.after_label}",
            "",
        ]

        if self.errors:
            lines.append("## Errors")
            for e in self.errors:
                lines.append(f"- {e}")
            lines.append("")

        # Score delta
        if self.score_before is not None and self.score_after is not None:
            arrow = "→"
            sign = "+" if (self.score_delta or 0) >= 0 else ""
            lines += [
                "## Score",
                "",
                f"**WCAG score:** {self.score_before}% {arrow} {self.score_after}% "
                f"({sign}{self.score_delta}pp)",
                "",
            ]
        else:
            lines += [
                "## Score",
                "",
                "_Score delta unavailable — at least one side was a screenshot "
                "without DOM data._",
                "",
            ]

        # Issue diff
        lines.append("## Issue Diff")
        lines.append("")
        lines.append(
            f"- **New:** {len(self.issues.new)} issue(s) introduced by the change"
        )
        lines.append(
            f"- **Fixed:** {len(self.issues.fixed)} issue(s) resolved"
        )
        lines.append(
            f"- **Persistent:** {len(self.issues.persistent)} unchanged"
        )
        lines.append("")

        if self.issues.new:
            lines.append("### New Issues")
            lines.append("")
            for issue in self.issues.new[:20]:
                lines.append(
                    f"- **{issue.get('criterion', '?')}** "
                    f"`{issue.get('element', '')}` "
                    f"— {issue.get('issue', '')[:80]}"
                )
            if len(self.issues.new) > 20:
                lines.append(f"- … +{len(self.issues.new) - 20} more")
            lines.append("")

        if self.issues.fixed:
            lines.append("### Fixed Issues")
            lines.append("")
            for issue in self.issues.fixed[:20]:
                lines.append(
                    f"- ~~**{issue.get('criterion', '?')}** "
                    f"`{issue.get('element', '')}`~~"
                )
            if len(self.issues.fixed) > 20:
                lines.append(f"- … +{len(self.issues.fixed) - 20} more")
            lines.append("")

        # Visual diff
        if self.visual_diff_path:
            lines += [
                "## Visual Diff",
                "",
                f"Found **{self.visual_diff_regions}** changed region(s). "
                f"Saved overlay: `{self.visual_diff_path}`",
                "",
            ]

        lines.append(f"**Exit code:** {self.exit_code}")
        return "\n".join(lines)


# ── Fingerprint diffing ──


def diff_fingerprints(
    before_fps: list[ViolationFingerprint],
    after_fps: list[ViolationFingerprint],
) -> IssueDiff:
    before_map = {fp.key: fp for fp in before_fps}
    after_map = {fp.key: fp for fp in after_fps}
    before_keys = set(before_map.keys())
    after_keys = set(after_map.keys())

    new = [after_map[k].to_dict() for k in sorted(after_keys - before_keys)]
    fixed = [before_map[k].to_dict() for k in sorted(before_keys - after_keys)]
    persistent = [after_map[k].to_dict() for k in sorted(after_keys & before_keys)]
    return IssueDiff(new=new, fixed=fixed, persistent=persistent)


def fingerprints_from_side(wcag_report, dom_data: dict) -> list[ViolationFingerprint]:
    """Extract all violation fingerprints for one side of the diff."""
    severity_gate = {"critical", "serious"}
    fps = _fingerprint_wcag_violations(wcag_report) if wcag_report else []
    fps += _fingerprint_axe_violations(dom_data or {}, severity_gate)
    return fps


# ── Visual diff ──


def _compute_visual_diff(
    before_path: Path | None,
    after_path: Path | None,
    output_path: Path,
    *,
    threshold: int = 20,
    min_region_size: int = 200,
) -> tuple[int, str | None]:
    """Overlay bounding boxes of changed regions on the after image.

    Returns (region_count, output_path_str_or_none). Skipped (returns 0, None)
    if either image is missing or sizes mismatch too severely to align.
    """
    if not before_path or not after_path:
        return 0, None
    if not before_path.exists() or not after_path.exists():
        return 0, None

    before_img = Image.open(before_path).convert("RGB")
    after_img = Image.open(after_path).convert("RGB")

    # Normalise to the smaller shared size to avoid alignment artefacts from
    # different viewport heights.
    width = min(before_img.width, after_img.width)
    height = min(before_img.height, after_img.height)
    if width < 10 or height < 10:
        return 0, None
    before_crop = before_img.crop((0, 0, width, height))
    after_crop = after_img.crop((0, 0, width, height))

    diff = ImageChops.difference(before_crop, after_crop).convert("L")
    # Threshold: ignore pixels with small differences (antialiasing flicker)
    mask = diff.point(lambda p: 255 if p > threshold else 0, mode="L")

    # Find connected change blobs via bounding boxes at grid resolution.
    bbox = mask.getbbox()
    if bbox is None:
        return 0, None

    regions = _split_mask_into_boxes(
        mask, min_region_size=min_region_size
    )
    if not regions:
        return 0, None

    overlay = after_crop.copy()
    draw = ImageDraw.Draw(overlay)
    for (x0, y0, x1, y1) in regions:
        draw.rectangle((x0, y0, x1, y1), outline=(255, 0, 0), width=3)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(output_path)
    return len(regions), str(output_path)


def _split_mask_into_boxes(
    mask: Image.Image, *, min_region_size: int, grid: int = 32
) -> list[tuple[int, int, int, int]]:
    """Coarse grid sweep — cluster non-zero mask cells into bounding boxes.

    A lightweight alternative to a full connected-component analysis: walk
    the mask in `grid`x`grid` cells, mark cells with enough changed pixels,
    then merge adjacent marked cells into rectangular regions.
    """
    w, h = mask.size
    cells_x = (w + grid - 1) // grid
    cells_y = (h + grid - 1) // grid

    pixels = mask.load()
    grid_marks: list[list[bool]] = [
        [False] * cells_x for _ in range(cells_y)
    ]
    min_cell_pixels = max(1, min_region_size // 8)

    for cy in range(cells_y):
        for cx in range(cells_x):
            x0 = cx * grid
            y0 = cy * grid
            x1 = min(x0 + grid, w)
            y1 = min(y0 + grid, h)
            changed = 0
            for y in range(y0, y1, 2):  # subsample
                for x in range(x0, x1, 2):
                    if pixels[x, y] > 0:
                        changed += 1
                        if changed >= min_cell_pixels:
                            break
                if changed >= min_cell_pixels:
                    break
            if changed >= min_cell_pixels:
                grid_marks[cy][cx] = True

    # Flood-fill merged regions
    visited = [[False] * cells_x for _ in range(cells_y)]
    regions: list[tuple[int, int, int, int]] = []
    for cy in range(cells_y):
        for cx in range(cells_x):
            if not grid_marks[cy][cx] or visited[cy][cx]:
                continue
            stack = [(cx, cy)]
            min_cx, max_cx = cx, cx
            min_cy, max_cy = cy, cy
            while stack:
                x, y = stack.pop()
                if x < 0 or y < 0 or x >= cells_x or y >= cells_y:
                    continue
                if visited[y][x] or not grid_marks[y][x]:
                    continue
                visited[y][x] = True
                min_cx = min(min_cx, x)
                max_cx = max(max_cx, x)
                min_cy = min(min_cy, y)
                max_cy = max(max_cy, y)
                stack.extend([(x+1, y), (x-1, y), (x, y+1), (x, y-1)])
            regions.append((
                min_cx * grid, min_cy * grid,
                min(max_cx * grid + grid, w),
                min(max_cy * grid + grid, h),
            ))
    return regions


# ── Main entry ──


def build_diff_report(
    *,
    before_label: str,
    after_label: str,
    before_wcag=None,
    before_dom: dict | None = None,
    before_image: Path | None = None,
    after_wcag=None,
    after_dom: dict | None = None,
    after_image: Path | None = None,
    visual_diff_output: Path | None = None,
    score_tolerance: float = DEFAULT_SCORE_TOLERANCE,
    errors: list[str] | None = None,
) -> DiffReport:
    """Build a DiffReport from the two sides' analysis results."""
    errs = list(errors or [])

    score_before = before_wcag.score_percentage if before_wcag else None
    score_after = after_wcag.score_percentage if after_wcag else None
    score_delta: float | None = None
    if score_before is not None and score_after is not None:
        score_delta = round(score_after - score_before, 1)

    before_fps = fingerprints_from_side(before_wcag, before_dom or {})
    after_fps = fingerprints_from_side(after_wcag, after_dom or {})
    issue_diff = diff_fingerprints(before_fps, after_fps)

    # Visual diff
    regions = 0
    diff_path_str: str | None = None
    if visual_diff_output is not None:
        regions, diff_path_str = _compute_visual_diff(
            before_image, after_image, visual_diff_output,
        )

    # Exit code matches CI gate semantics.
    if errs:
        exit_code = EXIT_TECHNICAL_ERROR
    elif issue_diff.new:
        exit_code = EXIT_THRESHOLD_FAILED
    elif score_delta is not None and score_delta < -score_tolerance:
        exit_code = EXIT_THRESHOLD_FAILED
    else:
        exit_code = EXIT_PASS

    return DiffReport(
        schema_version=SCHEMA_VERSION,
        before_label=before_label,
        after_label=after_label,
        score_before=score_before,
        score_after=score_after,
        score_delta=score_delta,
        issues=issue_diff,
        visual_diff_path=diff_path_str,
        visual_diff_regions=regions,
        exit_code=exit_code,
        errors=errs,
    )
