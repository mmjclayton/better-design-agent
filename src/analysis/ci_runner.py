"""
CI/CD gate evaluator.

Default mode is **pragmatic**: gates only on issues the current PR *introduces*,
not on pre-existing backlog. Pre-existing violations are grandfathered until
someone fixes them, so the gate doesn't nag every PR about 20 contrast issues
shipped months ago. This is the single biggest noise reduction for teams
adopting a design-quality gate.

Pragmatic rules (all on by default, all toggleable):
  1. **New-only** — compare this run's violation fingerprints to the baseline
     and fail only on violations not present before.
  2. **Severity-filtered** — only axe-core `critical` + `serious` gate the
     build. Moderate/minor surface in the report but don't fail CI.
  3. **Score-drop tolerance** — allow ±2% noise band on the WCAG score.
     Crawl timing, ads, and dynamic content cause flicker.
  4. **AAA ignored** — already excluded from scoring, also excluded from
     gating.

Pass `--strict` to the CLI to disable pragmatic mode and fail on any A/AA
violation or any score drop (the old "strict" behaviour is preserved for
teams that want a zero-tolerance gate).

Exit codes:
    0 — all configured thresholds passed
    1 — one or more thresholds failed
    2 — technical error (site blocked, missing baseline for first run
        is NOT an error — it's treated as informational and exits 0)
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
import json


SCHEMA_VERSION = 2

EXIT_PASS = 0
EXIT_THRESHOLD_FAILED = 1
EXIT_TECHNICAL_ERROR = 2


SEVERITY_ORDER = {"minor": 0, "moderate": 1, "serious": 2, "critical": 3}


@dataclass
class PragmaticConfig:
    """Tuning knobs for pragmatic-mode gating. All have sensible defaults."""

    enabled: bool = True
    severity_floor: str = "serious"  # minor | moderate | serious | critical
    score_tolerance: float = 2.0  # percentage points

    def impacts_above_floor(self) -> set[str]:
        floor = SEVERITY_ORDER.get(self.severity_floor, SEVERITY_ORDER["serious"])
        return {k for k, v in SEVERITY_ORDER.items() if v >= floor}


@dataclass
class ThresholdResult:
    name: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ViolationFingerprint:
    """Stable identity for a violation across runs.

    Two violations with the same (criterion, element, issue) are the same
    underlying problem.
    """
    criterion: str
    element: str
    issue: str

    @property
    def key(self) -> str:
        return f"{self.criterion}|{self.element}|{self.issue}"

    def to_dict(self) -> dict:
        return {"criterion": self.criterion, "element": self.element, "issue": self.issue}


@dataclass
class CiResult:
    schema_version: int
    url: str
    mode: str  # "pragmatic" | "strict"
    score: float
    score_previous: float | None
    score_delta: float | None
    wcag_violation_total: int
    aa_violation_total: int
    axe_critical: int
    axe_serious: int
    new_violations: list[dict]
    fixed_violations: list[dict]
    pre_existing_violations: list[dict]
    thresholds: list[ThresholdResult]
    exit_code: int
    errors: list[str] = field(default_factory=list)
    pragmatic_config: dict | None = None

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "url": self.url,
            "mode": self.mode,
            "score": self.score,
            "score_previous": self.score_previous,
            "score_delta": self.score_delta,
            "wcag_violation_total": self.wcag_violation_total,
            "aa_violation_total": self.aa_violation_total,
            "axe_critical": self.axe_critical,
            "axe_serious": self.axe_serious,
            "new_violations": self.new_violations,
            "fixed_violations": self.fixed_violations,
            "pre_existing_violations": self.pre_existing_violations,
            "thresholds": [t.to_dict() for t in self.thresholds],
            "exit_code": self.exit_code,
            "errors": self.errors,
            "pragmatic_config": self.pragmatic_config,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_human(self) -> str:
        lines = [
            f"CI Gate — {self.url}  [{self.mode}]",
            f"Score: {self.score}%"
            + (f" (was {self.score_previous}%, Δ {self.score_delta:+.1f})"
               if self.score_previous is not None else " (no baseline)"),
            f"Violations: {len(self.new_violations)} new, "
            f"{len(self.fixed_violations)} fixed, "
            f"{len(self.pre_existing_violations)} pre-existing",
            "",
        ]

        if self.errors:
            lines.append("Errors:")
            for e in self.errors:
                lines.append(f"  - {e}")
            lines.append("")

        if self.new_violations:
            lines.append(f"New violations (gating in {self.mode} mode):")
            for v in self.new_violations[:10]:
                lines.append(
                    f"  + {v.get('criterion', '?')}: "
                    f"{v.get('element', '')} {v.get('issue', '')}"[:110]
                )
            if len(self.new_violations) > 10:
                lines.append(f"  … +{len(self.new_violations) - 10} more")
            lines.append("")

        if self.fixed_violations:
            lines.append(f"Fixed in this run: {len(self.fixed_violations)}")
            lines.append("")

        if self.thresholds:
            lines.append("Thresholds:")
            for t in self.thresholds:
                mark = "PASS" if t.passed else "FAIL"
                lines.append(f"  [{mark}] {t.name}: {t.detail}")
            lines.append("")

        lines.append(f"Exit: {self.exit_code}")
        return "\n".join(lines)


# ── Fingerprinting + diffing ──


def _fingerprint_wcag_violations(wcag_report) -> list[ViolationFingerprint]:
    """Extract a fingerprint per failing WCAG violation."""
    out: list[ViolationFingerprint] = []
    if not wcag_report:
        return out
    for result in wcag_report.results:
        if result.status != "fail":
            continue
        if not result.violations:
            # Criterion-level failure with no per-element list (e.g. missing lang).
            out.append(ViolationFingerprint(
                criterion=result.criterion,
                element="",
                issue=result.details,
            ))
            continue
        for v in result.violations:
            out.append(ViolationFingerprint(
                criterion=result.criterion,
                element=str(v.get("element", "")),
                issue=str(v.get("issue", v.get("size", ""))),
            ))
    return out


def _fingerprint_axe_violations(
    dom_data: dict,
    impacts_gate: set[str],
) -> list[ViolationFingerprint]:
    """Extract fingerprints from axe-core violations matching the gate."""
    axe = dom_data.get("axe_results", {}) if isinstance(dom_data, dict) else {}
    violations = axe.get("violations", []) if isinstance(axe, dict) else []
    out: list[ViolationFingerprint] = []
    for v in violations:
        if v.get("impact") not in impacts_gate:
            continue
        for node in v.get("nodes", [{}]) or [{}]:
            target = node.get("target", [""])
            element = target[0] if isinstance(target, list) and target else ""
            out.append(ViolationFingerprint(
                criterion=f"axe:{v.get('id', '?')}",
                element=str(element),
                issue=v.get("impact", "") + " " + v.get("description", "")[:60],
            ))
    return out


def _baseline_keys(previous_run) -> set[str]:
    """Extract fingerprint keys from a stored previous run."""
    if previous_run is None or not getattr(previous_run, "issues", None):
        return set()
    keys: set[str] = set()
    for issue in previous_run.issues:
        fp = ViolationFingerprint(
            criterion=str(issue.get("criterion", "")),
            element=str(issue.get("element", "")),
            issue=str(issue.get("details", issue.get("issue", ""))),
        )
        keys.add(fp.key)
    return keys


def _count_aa_violations(wcag_report) -> int:
    if not wcag_report:
        return 0
    return sum(
        r.count for r in wcag_report.results
        if r.status == "fail" and r.level in ("A", "AA")
    )


def _count_axe_impact(dom_data: dict) -> tuple[int, int]:
    axe = dom_data.get("axe_results", {}) if isinstance(dom_data, dict) else {}
    violations = axe.get("violations", []) if isinstance(axe, dict) else []
    critical = sum(1 for v in violations if v.get("impact") == "critical")
    serious = sum(1 for v in violations if v.get("impact") == "serious")
    return critical, serious


# ── Main evaluator ──


def evaluate(
    *,
    url: str,
    wcag_report,
    dom_data: dict,
    previous_run=None,
    min_score: float | None = None,
    pragmatic: PragmaticConfig | None = None,
    strict: bool = False,
    blocked: bool = False,
) -> CiResult:
    """Evaluate CI thresholds and return a structured result.

    - `pragmatic`: tuning for pragmatic mode. Defaults to `PragmaticConfig()`.
    - `strict=True`: disables pragmatic mode entirely. Every A/AA violation
      and any score drop fails. Use when the caller wants zero-tolerance.
    """
    cfg = pragmatic or PragmaticConfig()
    mode = "strict" if strict else "pragmatic"
    score = wcag_report.score_percentage if wcag_report else 0.0
    wcag_total = wcag_report.total_violations if wcag_report else 0
    aa_total = _count_aa_violations(wcag_report)
    axe_critical, axe_serious = _count_axe_impact(dom_data)

    # Build current fingerprint set (WCAG + axe, severity-filtered in pragmatic).
    impacts_gate = (
        cfg.impacts_above_floor() if not strict else {"critical", "serious", "moderate", "minor"}
    )
    current_fps = (
        _fingerprint_wcag_violations(wcag_report)
        + _fingerprint_axe_violations(dom_data, impacts_gate)
    )
    current_keys = {fp.key for fp in current_fps}
    current_by_key = {fp.key: fp for fp in current_fps}

    baseline_keys = _baseline_keys(previous_run)

    new_keys = current_keys - baseline_keys
    fixed_keys = baseline_keys - current_keys
    persistent_keys = current_keys & baseline_keys

    new_violations = [current_by_key[k].to_dict() for k in sorted(new_keys)]
    pre_existing_violations = [
        current_by_key[k].to_dict() for k in sorted(persistent_keys)
    ]
    fixed_violations = [{"key": k} for k in sorted(fixed_keys)]

    prev_score = previous_run.wcag_score if previous_run else None
    score_delta = round(score - prev_score, 1) if prev_score is not None else None

    errors: list[str] = []
    thresholds: list[ThresholdResult] = []

    if blocked:
        errors.append("Site blocked automated access — could not run audit.")

    # Always supported: user-specified hard score floor.
    if min_score is not None:
        passed = score >= min_score
        thresholds.append(ThresholdResult(
            name="min-score",
            passed=passed,
            detail=f"score {score}% vs required {min_score}%",
        ))

    if strict:
        # Strict: any A/AA violation fails; any score drop fails.
        thresholds.append(ThresholdResult(
            name="strict/no-aa-violations",
            passed=(aa_total + axe_critical + axe_serious == 0),
            detail=(
                f"{aa_total} WCAG A/AA + {axe_critical} axe critical + "
                f"{axe_serious} axe serious"
            ),
        ))
        if prev_score is not None:
            thresholds.append(ThresholdResult(
                name="strict/no-score-drop",
                passed=(score >= prev_score),
                detail=f"current {score}% vs previous {prev_score}%",
            ))
    else:
        # Pragmatic: only NEW severity-qualifying violations fail the gate.
        has_baseline = previous_run is not None
        if has_baseline:
            thresholds.append(ThresholdResult(
                name=f"pragmatic/no-new-violations (>= {cfg.severity_floor})",
                passed=(len(new_violations) == 0),
                detail=(
                    f"{len(new_violations)} new vs baseline "
                    f"({len(pre_existing_violations)} pre-existing, "
                    f"{len(fixed_violations)} fixed)"
                ),
            ))
            thresholds.append(ThresholdResult(
                name=f"pragmatic/score-drop (tolerance {cfg.score_tolerance}pp)",
                passed=(score_delta is None or score_delta >= -cfg.score_tolerance),
                detail=(
                    f"delta {score_delta:+.1f}pp"
                    if score_delta is not None else "no baseline"
                ),
            ))
        else:
            # First run: baseline stored, nothing to gate on yet.
            thresholds.append(ThresholdResult(
                name="pragmatic/baseline-captured",
                passed=True,
                detail="first run for this URL — saving as baseline, exiting 0",
            ))

    # Exit code: technical errors win, then threshold failures, then pass.
    if errors:
        exit_code = EXIT_TECHNICAL_ERROR
    elif any(not t.passed for t in thresholds):
        exit_code = EXIT_THRESHOLD_FAILED
    else:
        exit_code = EXIT_PASS

    return CiResult(
        schema_version=SCHEMA_VERSION,
        url=url,
        mode=mode,
        score=score,
        score_previous=prev_score,
        score_delta=score_delta,
        wcag_violation_total=wcag_total,
        aa_violation_total=aa_total,
        axe_critical=axe_critical,
        axe_serious=axe_serious,
        new_violations=new_violations,
        fixed_violations=fixed_violations,
        pre_existing_violations=pre_existing_violations,
        thresholds=thresholds,
        exit_code=exit_code,
        errors=errors,
        pragmatic_config=None if strict else asdict(cfg),
    )
