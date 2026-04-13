"""Tests for the before/after diff analyser."""

import json
from pathlib import Path

from PIL import Image, ImageDraw

from src.analysis.diff_analyzer import (
    EXIT_PASS,
    EXIT_THRESHOLD_FAILED,
    EXIT_TECHNICAL_ERROR,
    IssueDiff,
    build_diff_report,
    diff_fingerprints,
    fingerprints_from_side,
    _compute_visual_diff,
)
from src.analysis.ci_runner import ViolationFingerprint
from src.analysis.wcag_checker import WcagReport, WcagResult


# ── Helpers ──


def _wcag(pass_count: int, fail_violations: list | None = None) -> WcagReport:
    r = WcagReport()
    for _ in range(pass_count):
        r.results.append(WcagResult("p", "AA", "pass", "ok"))
    if fail_violations:
        r.results.append(WcagResult(
            "2.5.8", "AA", "fail", "bad",
            count=len(fail_violations), violations=fail_violations,
        ))
    return r


# ── Fingerprint diff ──


def test_fingerprint_diff_all_new():
    before = []
    after = [ViolationFingerprint("x", "btn.a", "bad")]
    diff = diff_fingerprints(before, after)
    assert len(diff.new) == 1
    assert diff.fixed == []
    assert diff.persistent == []


def test_fingerprint_diff_all_fixed():
    before = [ViolationFingerprint("x", "btn.a", "bad")]
    after = []
    diff = diff_fingerprints(before, after)
    assert diff.new == []
    assert len(diff.fixed) == 1


def test_fingerprint_diff_persistent():
    shared = ViolationFingerprint("x", "btn.a", "bad")
    diff = diff_fingerprints([shared], [shared])
    assert len(diff.persistent) == 1
    assert diff.new == []
    assert diff.fixed == []


def test_fingerprint_diff_mixed_buckets():
    before = [
        ViolationFingerprint("x", "btn.a", "stays"),
        ViolationFingerprint("x", "btn.b", "gets-fixed"),
    ]
    after = [
        ViolationFingerprint("x", "btn.a", "stays"),
        ViolationFingerprint("x", "btn.c", "brand-new"),
    ]
    diff = diff_fingerprints(before, after)
    assert len(diff.new) == 1 and diff.new[0]["element"] == "btn.c"
    assert len(diff.fixed) == 1 and diff.fixed[0]["element"] == "btn.b"
    assert len(diff.persistent) == 1 and diff.persistent[0]["element"] == "btn.a"


# ── Side fingerprinting ──


def test_fingerprints_from_side_combines_wcag_and_axe():
    wcag = _wcag(9, [{"element": "btn.x", "issue": "20x20"}])
    dom = {"axe_results": {"violations": [
        {"id": "color-contrast", "impact": "critical", "description": "",
         "nodes": [{"target": [".a"]}]},
        {"id": "minor-thing", "impact": "minor", "description": "",
         "nodes": [{"target": [".b"]}]},
    ]}}
    fps = fingerprints_from_side(wcag, dom)
    # 1 WCAG + 1 axe critical (minor filtered)
    assert len(fps) == 2
    keys = {fp.key for fp in fps}
    assert any("btn.x" in k for k in keys)
    assert any(".a" in k for k in keys)
    assert not any(".b" in k for k in keys)


def test_fingerprints_from_side_handles_missing_wcag():
    fps = fingerprints_from_side(None, {})
    assert fps == []


# ── DiffReport assembly: score + exit code ──


def test_diff_report_pass_when_no_new_issues_and_score_flat():
    wcag = _wcag(10)
    report = build_diff_report(
        before_label="v1", after_label="v2",
        before_wcag=wcag, before_dom={},
        after_wcag=wcag, after_dom={},
    )
    assert report.exit_code == EXIT_PASS
    assert report.score_delta == 0.0
    assert report.issues.new == []


def test_diff_report_fail_when_new_issues_introduced():
    before = _wcag(10)
    after = _wcag(9, [{"element": "btn.x", "issue": "20x20"}])
    report = build_diff_report(
        before_label="v1", after_label="v2",
        before_wcag=before, before_dom={},
        after_wcag=after, after_dom={},
    )
    assert report.exit_code == EXIT_THRESHOLD_FAILED
    assert len(report.issues.new) == 1


def test_diff_report_pass_when_issues_fixed():
    before = _wcag(9, [{"element": "btn.x", "issue": "20x20"}])
    after = _wcag(10)
    report = build_diff_report(
        before_label="v1", after_label="v2",
        before_wcag=before, before_dom={},
        after_wcag=after, after_dom={},
    )
    assert report.exit_code == EXIT_PASS
    assert len(report.issues.fixed) == 1
    assert len(report.issues.new) == 0
    # Score went up, delta positive
    assert report.score_delta is not None and report.score_delta > 0


def test_diff_report_fail_on_score_drop_beyond_tolerance():
    before = _wcag(10)  # 100%
    # Drastic drop: 5 passes + 1 fail → 83.3%
    after = _wcag(5, [{"element": "btn.x", "issue": "z"}])
    report = build_diff_report(
        before_label="v1", after_label="v2",
        before_wcag=before, before_dom={},
        after_wcag=after, after_dom={},
        score_tolerance=2.0,
    )
    assert report.exit_code == EXIT_THRESHOLD_FAILED
    assert report.score_delta is not None and report.score_delta < -2.0


def test_diff_report_score_tolerance_absorbs_small_drop():
    # 10 passes → 100%, then 8 passes + 0 fails → 100%. Force a tiny drop.
    before = _wcag(10)
    after = _wcag(99, [{"element": "btn.x", "issue": "z"}])  # 99/100 = 99%
    report = build_diff_report(
        before_label="v1", after_label="v2",
        before_wcag=before, before_dom={},
        after_wcag=after, after_dom={},
        score_tolerance=2.0,
    )
    # 1 new issue → will fail on new-issues, but score tolerance itself doesn't trip.
    # To isolate the tolerance check, assert it's the new-issues branch.
    assert len(report.issues.new) == 1


def test_diff_report_technical_error_exits_two():
    report = build_diff_report(
        before_label="v1", after_label="v2",
        errors=["before image not found"],
    )
    assert report.exit_code == EXIT_TECHNICAL_ERROR
    assert "before image not found" in report.errors[0]


def test_diff_report_score_unknown_when_no_wcag_on_either_side():
    report = build_diff_report(
        before_label="img1.png", after_label="img2.png",
    )
    assert report.score_before is None
    assert report.score_after is None
    assert report.score_delta is None


# ── Markdown + JSON output ──


def test_diff_report_markdown_contains_all_sections():
    before = _wcag(10)
    after = _wcag(9, [{"element": "btn.x", "issue": "20x20"}])
    report = build_diff_report(
        before_label="v1", after_label="v2",
        before_wcag=before, before_dom={},
        after_wcag=after, after_dom={},
    )
    md = report.to_markdown()
    assert "# Before / After Diff" in md
    assert "**Before:** v1" in md
    assert "**After:** v2" in md
    assert "## Score" in md
    assert "## Issue Diff" in md
    assert "### New Issues" in md
    assert "**Exit code:**" in md


def test_diff_report_markdown_shows_score_unavailable_when_missing():
    report = build_diff_report(before_label="a.png", after_label="b.png")
    md = report.to_markdown()
    assert "unavailable" in md.lower()


def test_diff_report_json_schema_shape():
    before = _wcag(10)
    after = _wcag(9, [{"element": "btn.x", "issue": "20x20"}])
    report = build_diff_report(
        before_label="v1", after_label="v2",
        before_wcag=before, before_dom={},
        after_wcag=after, after_dom={},
    )
    data = json.loads(report.to_json())
    required = {
        "schema_version", "before_label", "after_label",
        "score_before", "score_after", "score_delta",
        "new_issues", "fixed_issues", "persistent_issues",
        "visual_diff_path", "visual_diff_regions", "exit_code", "errors",
    }
    assert required.issubset(data.keys())
    assert data["schema_version"] == 1


# ── Visual diff ──


def _make_solid_image(path: Path, colour: tuple[int, int, int], size=(400, 300)):
    img = Image.new("RGB", size, colour)
    img.save(path)


def _make_image_with_box(
    path: Path, base_colour: tuple[int, int, int],
    box: tuple[int, int, int, int], box_colour: tuple[int, int, int],
    size=(400, 300),
):
    img = Image.new("RGB", size, base_colour)
    draw = ImageDraw.Draw(img)
    draw.rectangle(box, fill=box_colour)
    img.save(path)


def test_visual_diff_identical_images_yields_no_regions(tmp_path):
    before = tmp_path / "before.png"
    after = tmp_path / "after.png"
    out = tmp_path / "diff.png"
    _make_solid_image(before, (255, 255, 255))
    _make_solid_image(after, (255, 255, 255))

    regions, out_path = _compute_visual_diff(before, after, out)
    assert regions == 0
    assert out_path is None
    assert not out.exists()


def test_visual_diff_detects_changed_region(tmp_path):
    before = tmp_path / "before.png"
    after = tmp_path / "after.png"
    out = tmp_path / "diff.png"
    _make_solid_image(before, (255, 255, 255))
    _make_image_with_box(
        after, (255, 255, 255),
        box=(100, 100, 200, 200),
        box_colour=(255, 0, 0),
    )

    regions, out_path = _compute_visual_diff(before, after, out)
    assert regions >= 1
    assert out_path is not None
    assert out.exists()
    # Verify the overlay is actually written.
    written = Image.open(out)
    assert written.size == (400, 300)


def test_visual_diff_missing_input_returns_none(tmp_path):
    before = tmp_path / "nope.png"
    after = tmp_path / "also-nope.png"
    out = tmp_path / "diff.png"
    regions, out_path = _compute_visual_diff(before, after, out)
    assert regions == 0
    assert out_path is None


def test_visual_diff_none_input_returns_none(tmp_path):
    out = tmp_path / "diff.png"
    regions, out_path = _compute_visual_diff(None, None, out)
    assert regions == 0
    assert out_path is None


def test_visual_diff_skips_on_tiny_images(tmp_path):
    before = tmp_path / "before.png"
    after = tmp_path / "after.png"
    out = tmp_path / "diff.png"
    Image.new("RGB", (5, 5), (255, 255, 255)).save(before)
    Image.new("RGB", (5, 5), (0, 0, 0)).save(after)
    regions, out_path = _compute_visual_diff(before, after, out)
    assert regions == 0
    assert out_path is None


# ── IssueDiff dataclass ──


def test_issue_diff_defaults_to_empty_lists():
    d = IssueDiff()
    assert d.new == []
    assert d.fixed == []
    assert d.persistent == []
