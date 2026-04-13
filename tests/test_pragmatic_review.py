"""Tests for pragmatic-mode output rendering + the review command's
plan-resolution and target-detection helpers.

The interactive prompts are tested via `--non-interactive` path, which
skips the Rich prompts entirely.
"""

from typer.testing import CliRunner

from src.analysis.wcag_checker import WcagReport, WcagResult
from src.analysis.component_detector import ComponentReport, ComponentScore
from src.agents.critique import CritiqueAgent, PRAGMATIC_MODE_INSTRUCTION
from src.cli import (
    app,
    REVIEW_MODES,
    OUTPUT_FORMATS,
    _detect_target_type,
    _resolve_review_plan,
)


runner = CliRunner(mix_stderr=False)


# ── WcagReport.to_pragmatic_markdown ──


def test_wcag_pragmatic_drops_passes_warnings_aaa():
    report = WcagReport()
    report.results.extend([
        WcagResult("pass-x", "AA", "pass", "ok"),
        WcagResult("warn-x", "AA", "warning", "nearly"),
        WcagResult("na-x", "AA", "na", "skipped"),
        WcagResult("aaa-x", "AAA", "fail", "aspirational",
                   count=1, violations=[{"element": "a"}]),
        WcagResult("fail-aa", "AA", "fail", "needs fix",
                   count=2,
                   violations=[
                       {"element": "btn.a", "issue": "bad"},
                       {"element": "btn.b", "issue": "worse"},
                   ]),
    ])
    md = report.to_pragmatic_markdown()
    assert "Pragmatic View" in md
    assert "fail-aa" in md
    assert "aaa-x" not in md
    assert "pass-x" not in md
    assert "warn-x" not in md
    assert "btn.a" in md
    assert "btn.b" in md


def test_wcag_pragmatic_empty_when_no_aa_failures():
    report = WcagReport()
    report.results.append(WcagResult("pass-x", "AA", "pass", "ok"))
    report.results.append(WcagResult("aaa-x", "AAA", "fail", "skip"))
    md = report.to_pragmatic_markdown()
    assert "nothing to fix" in md.lower()


def test_wcag_pragmatic_dedupes_and_caps_violations():
    report = WcagReport()
    violations = [
        {"element": "btn.a", "issue": "dup"},
        {"element": "btn.a", "issue": "dup"},  # duplicate
        *[{"element": f"btn.{i}", "issue": "x"} for i in range(10)],
    ]
    report.results.append(WcagResult(
        "fail-x", "AA", "fail", "many", count=len(violations), violations=violations,
    ))
    md = report.to_pragmatic_markdown()
    # 11 unique (btn.a once + btn.0-9), displayed cap is 5 + overflow line
    assert "… +" in md


# ── ComponentReport.to_pragmatic_markdown ──


def test_components_pragmatic_only_below_threshold():
    report = ComponentReport(components=[
        ComponentScore(name="nav", type="nav", selector="nav", score=9, max_score=10),  # 90%
        ComponentScore(name="form", type="form", selector="form", score=4, max_score=10),  # 40%
        ComponentScore(name="card", type="card", selector=".card", score=6, max_score=10),  # 60%
        ComponentScore(name="btn", type="button-group", selector=".btns", score=2, max_score=10),  # 20%
    ])
    md = report.to_pragmatic_markdown(threshold=60)
    assert "form" in md  # 40% — below
    assert "btn" in md   # 20% — below
    assert "nav" not in md  # 90% — above
    # "card" is 60% which equals the threshold — excluded (< threshold, strict).
    assert "### card" not in md


def test_components_pragmatic_all_above_threshold():
    report = ComponentReport(components=[
        ComponentScore(name="nav", type="nav", selector="nav", score=9, max_score=10),
        ComponentScore(name="form", type="form", selector="form", score=10, max_score=10),
    ])
    md = report.to_pragmatic_markdown()
    assert "Nothing flagged" in md


def test_components_pragmatic_caps_issues_per_component():
    report = ComponentReport(components=[
        ComponentScore(
            name="form", type="form", selector="form", score=1, max_score=10,
            issues=[f"issue {i}" for i in range(10)],
        ),
    ])
    md = report.to_pragmatic_markdown()
    assert "… +5 more" in md


# ── CritiqueAgent pragmatic flag ──


def test_critique_agent_pragmatic_flag_injects_instruction():
    agent = CritiqueAgent(tone="opinionated", pragmatic=True)
    prompt = agent.system_prompt()
    assert "PRAGMATIC mode" in prompt
    assert "severity ≥ 2" in prompt


def test_critique_agent_pragmatic_false_omits_instruction():
    agent = CritiqueAgent(tone="opinionated", pragmatic=False)
    prompt = agent.system_prompt()
    assert "PRAGMATIC mode" not in prompt


def test_pragmatic_instruction_constant_present():
    assert "Pragmatic mode" in PRAGMATIC_MODE_INSTRUCTION
    assert "Nielsen severity" in PRAGMATIC_MODE_INSTRUCTION


# ── Target detection ──


def test_detect_url_target():
    kind, err = _detect_target_type("https://example.com")
    assert kind == "url" and err is None


def test_detect_http_url():
    kind, err = _detect_target_type("http://localhost:3000")
    assert kind == "url" and err is None


def test_detect_image_path(tmp_path):
    p = tmp_path / "shot.png"
    p.write_bytes(b"fake")
    kind, err = _detect_target_type(str(p))
    assert kind == "image" and err is None


def test_detect_unsupported_file(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("not an image")
    kind, err = _detect_target_type(str(p))
    assert kind == "unknown"
    assert "not supported" in err.lower()


def test_detect_missing_file():
    kind, err = _detect_target_type("/nonexistent/path.png")
    assert kind == "unknown"
    assert "not found" in err.lower()


def test_detect_empty_target():
    kind, err = _detect_target_type("")
    assert kind == "unknown"
    assert "empty" in err.lower()


# ── Plan resolution ──


def test_plan_pragmatic_audit_url():
    argv = _resolve_review_plan(
        "pragmatic-audit", "https://x.com", "url", "terminal", None,
    )
    assert argv == ["wcag", "--url", "https://x.com", "--pragmatic"]


def test_plan_pragmatic_critique_with_context():
    argv = _resolve_review_plan(
        "pragmatic-critique", "https://x.com", "url", "markdown", "B2B dashboard",
    )
    assert "--pragmatic" in argv
    assert "--save" in argv
    assert "--context" in argv
    assert "B2B dashboard" in argv


def test_plan_deep_critique_pdf_output():
    argv = _resolve_review_plan(
        "deep-critique", "https://x.com", "url", "pdf", None,
    )
    assert "--deep" in argv
    assert "--save" in argv
    assert "--pdf" in argv
    assert "--context" not in argv


def test_plan_brand_compliance_ignores_save():
    argv = _resolve_review_plan(
        "brand-compliance", "https://x.com", "url", "pdf", None,
    )
    assert argv == ["brand-check", "--url", "https://x.com"]


def test_plan_everything_deep_flag():
    argv = _resolve_review_plan(
        "everything", "https://x.com", "url", "html", None,
    )
    assert "--deep" in argv
    assert "--save" in argv


def test_plan_image_target_uses_image_flag():
    argv = _resolve_review_plan(
        "pragmatic-critique", "./shot.png", "image", "terminal", None,
    )
    assert "--image" in argv
    assert "./shot.png" in argv
    assert "--url" not in argv


def test_plan_unknown_mode_returns_empty():
    argv = _resolve_review_plan(
        "garbage", "https://x.com", "url", "terminal", None,
    )
    assert argv == []


# ── Modes and format tables are well-formed ──


def test_review_modes_has_five_entries():
    assert len(REVIEW_MODES) == 5
    for key, info in REVIEW_MODES.items():
        assert "label" in info
        assert "description" in info


def test_output_formats_covers_expected_set():
    assert set(OUTPUT_FORMATS.keys()) == {"terminal", "html-only", "markdown", "html", "pdf"}


def test_plan_html_only_emits_html_only_flag():
    argv = _resolve_review_plan(
        "pragmatic-critique", "https://x.com", "url", "html-only", None,
    )
    assert "--save" in argv
    assert "--html-only" in argv
    assert "--pdf" not in argv


def test_plan_html_format_does_not_emit_html_only_flag():
    argv = _resolve_review_plan(
        "pragmatic-critique", "https://x.com", "url", "html", None,
    )
    assert "--save" in argv
    assert "--html-only" not in argv


# ── Non-interactive review CLI ──


def test_review_non_interactive_requires_mode_and_target():
    result = runner.invoke(app, ["review", "--non-interactive"])
    assert result.exit_code == 2
    assert "requires --mode" in result.stderr or "requires --mode" in result.stdout


def test_review_non_interactive_rejects_unknown_mode():
    result = runner.invoke(app, [
        "review", "--non-interactive",
        "--mode", "not-a-mode",
        "--target", "https://x.com",
    ])
    assert result.exit_code == 2
    assert "unknown mode" in (result.stderr + result.stdout).lower()


def test_review_non_interactive_rejects_bad_target():
    result = runner.invoke(app, [
        "review", "--non-interactive",
        "--mode", "pragmatic-audit",
        "--target", "/no/such/file.png",
    ])
    assert result.exit_code == 2
    assert "not found" in (result.stderr + result.stdout).lower()
