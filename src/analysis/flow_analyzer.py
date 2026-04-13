"""
User flow analyser.

Executes a multi-step journey defined in a YAML flow file, captures
screenshots at each step, and emits a step-by-step report with timings
plus industry-benchmark comparison.

Split into two layers (same pattern as pdf_report):
- Pure layer: YAML validation, step parsing, result aggregation,
  benchmark comparison, report rendering. Fully tested.
- Integration layer: Playwright execution. Manual / integration tested.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

import yaml


SCHEMA_VERSION = 1

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_TECHNICAL_ERROR = 2

DEFAULT_STEP_TIMEOUT_MS = 10_000

VALID_ACTIONS = {"navigate", "click", "fill", "assert_text"}
VALID_FLOW_TYPES = {"signup", "checkout", "login", "onboarding", "other"}

# Industry-norm step counts for common flows.
FLOW_BENCHMARKS = {
    "signup": {"max": 3, "description": "Signup flows should be 2-3 steps"},
    "checkout": {"max": 5, "description": "Checkout flows should be 3-5 steps"},
    "login": {"max": 2, "description": "Login flows should be 1-2 steps"},
    "onboarding": {"max": 5, "description": "Onboarding flows should be 3-5 steps"},
}


# ── YAML loading + validation ──


class FlowLoadError(Exception):
    """Raised when a flow YAML can't be loaded or validated."""


@dataclass
class FlowStep:
    name: str
    action: str
    selector: str | None = None
    value: str | None = None
    url: str | None = None
    timeout_ms: int = DEFAULT_STEP_TIMEOUT_MS

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FlowDefinition:
    name: str
    flow_type: str
    steps: list[FlowStep]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "flow_type": self.flow_type,
            "steps": [s.to_dict() for s in self.steps],
        }


def load_flow(path: Path) -> FlowDefinition:
    """Load + validate a flow YAML file. Raises FlowLoadError on any issue."""
    if not path.exists():
        raise FlowLoadError(
            f"Flow file not found at {path}. "
            "See examples/flow-example.yaml for the schema."
        )
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise FlowLoadError(f"Flow file is malformed YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise FlowLoadError("Flow file must be a YAML mapping at the top level.")

    name = raw.get("name")
    if not name:
        raise FlowLoadError("Flow is missing required 'name' field.")

    flow_type = raw.get("flow_type", "other")
    if flow_type not in VALID_FLOW_TYPES:
        raise FlowLoadError(
            f"Invalid flow_type '{flow_type}'. "
            f"Must be one of: {sorted(VALID_FLOW_TYPES)}"
        )

    steps_raw = raw.get("steps", [])
    if not isinstance(steps_raw, list) or not steps_raw:
        raise FlowLoadError("Flow must define a non-empty 'steps' list.")

    steps = []
    for i, step_raw in enumerate(steps_raw):
        if not isinstance(step_raw, dict):
            raise FlowLoadError(f"Step {i + 1} is not a mapping.")

        step_name = step_raw.get("name", f"Step {i + 1}")
        action = step_raw.get("action")
        if not action:
            raise FlowLoadError(f"Step '{step_name}' is missing 'action'.")
        if action not in VALID_ACTIONS:
            raise FlowLoadError(
                f"Step '{step_name}' has invalid action '{action}'. "
                f"Must be one of: {sorted(VALID_ACTIONS)}"
            )

        # Validate required fields per action type.
        if action == "navigate" and not step_raw.get("url"):
            raise FlowLoadError(f"Step '{step_name}' (navigate) requires 'url'.")
        if action == "click" and not step_raw.get("selector"):
            raise FlowLoadError(f"Step '{step_name}' (click) requires 'selector'.")
        if action == "fill" and not (step_raw.get("selector") and step_raw.get("value") is not None):
            raise FlowLoadError(f"Step '{step_name}' (fill) requires 'selector' and 'value'.")
        if action == "assert_text" and not step_raw.get("value"):
            raise FlowLoadError(f"Step '{step_name}' (assert_text) requires 'value'.")

        steps.append(FlowStep(
            name=step_name,
            action=action,
            selector=step_raw.get("selector"),
            value=str(step_raw["value"]) if step_raw.get("value") is not None else None,
            url=step_raw.get("url"),
            timeout_ms=int(step_raw.get("timeout_ms", DEFAULT_STEP_TIMEOUT_MS)),
        ))

    return FlowDefinition(name=name, flow_type=flow_type, steps=steps)


# ── Result aggregation ──


@dataclass
class StepResult:
    name: str
    action: str
    passed: bool
    duration_ms: int
    error: str | None = None
    screenshot_path: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BenchmarkComparison:
    flow_type: str
    step_count: int
    max_allowed: int | None
    within_benchmark: bool
    description: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FlowReport:
    schema_version: int
    flow_name: str
    flow_type: str
    base_url: str
    timestamp: str
    total_duration_ms: int
    step_results: list[StepResult]
    benchmark: BenchmarkComparison | None
    exit_code: int
    errors: list[str] = field(default_factory=list)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.step_results if r.passed)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.step_results if not r.passed)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "flow_name": self.flow_name,
            "flow_type": self.flow_type,
            "base_url": self.base_url,
            "timestamp": self.timestamp,
            "total_duration_ms": self.total_duration_ms,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "step_results": [s.to_dict() for s in self.step_results],
            "benchmark": self.benchmark.to_dict() if self.benchmark else None,
            "exit_code": self.exit_code,
            "errors": self.errors,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_markdown(self) -> str:
        lines = [
            f"# Flow: {self.flow_name}",
            "",
            f"**Type:** {self.flow_type}  |  **Base URL:** {self.base_url}",
            f"**Steps:** {len(self.step_results)}  "
            f"(**{self.passed_count}** passed, **{self.failed_count}** failed)  "
            f"|  **Duration:** {self.total_duration_ms}ms",
            "",
        ]

        if self.errors:
            lines.append("## Errors")
            for e in self.errors:
                lines.append(f"- {e}")
            lines.append("")

        if self.benchmark:
            b = self.benchmark
            marker = "[PASS]" if b.within_benchmark else "[FAIL]"
            lines.append("## Benchmark")
            lines.append("")
            lines.append(
                f"**{marker}** {b.description}. "
                f"Your flow: **{b.step_count}** steps "
                f"(max recommended: **{b.max_allowed}**)."
            )
            lines.append("")

        lines.append("## Step Results")
        lines.append("")
        lines.append("| # | Name | Action | Result | Duration |")
        lines.append("|---|------|--------|--------|----------|")
        for i, r in enumerate(self.step_results, 1):
            status = "PASS" if r.passed else "FAIL"
            lines.append(
                f"| {i} | {r.name} | `{r.action}` | {status} | {r.duration_ms}ms |"
            )
        lines.append("")

        failed = [r for r in self.step_results if not r.passed]
        if failed:
            lines.append("## Failed Steps")
            lines.append("")
            for r in failed:
                lines.append(f"### {r.name}")
                lines.append("")
                lines.append(f"- **Action:** `{r.action}`")
                if r.error:
                    lines.append(f"- **Error:** {r.error}")
                lines.append("")

        lines.append(f"**Exit code:** {self.exit_code}")
        return "\n".join(lines)


# ── Benchmark comparison ──


def compare_to_benchmark(
    flow_type: str, step_count: int,
) -> BenchmarkComparison | None:
    bench = FLOW_BENCHMARKS.get(flow_type)
    if not bench:
        return None
    return BenchmarkComparison(
        flow_type=flow_type,
        step_count=step_count,
        max_allowed=bench["max"],
        within_benchmark=step_count <= bench["max"],
        description=bench["description"],
    )


# ── Report assembly ──


def build_flow_report(
    *,
    flow: FlowDefinition,
    base_url: str,
    step_results: list[StepResult],
    total_duration_ms: int,
    errors: list[str] | None = None,
    now: datetime | None = None,
) -> FlowReport:
    """Assemble a FlowReport from raw execution results."""
    errs = list(errors or [])
    timestamp = (now or datetime.now()).isoformat(timespec="seconds")
    benchmark = compare_to_benchmark(flow.flow_type, len(flow.steps))

    if errs:
        exit_code = EXIT_TECHNICAL_ERROR
    elif any(not r.passed for r in step_results):
        exit_code = EXIT_FAIL
    elif benchmark and not benchmark.within_benchmark:
        exit_code = EXIT_FAIL
    else:
        exit_code = EXIT_PASS

    return FlowReport(
        schema_version=SCHEMA_VERSION,
        flow_name=flow.name,
        flow_type=flow.flow_type,
        base_url=base_url,
        timestamp=timestamp,
        total_duration_ms=total_duration_ms,
        step_results=step_results,
        benchmark=benchmark,
        exit_code=exit_code,
        errors=errs,
    )


# ── Playwright execution (integration layer) ──


def execute_flow(
    flow: FlowDefinition,
    base_url: str,
    output_dir: Path,
) -> FlowReport:
    """Execute a flow via Playwright and return a FlowReport.

    Integration point — spawns a browser. Failures (import, launch) are
    caught and returned as technical errors.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return build_flow_report(
            flow=flow, base_url=base_url, step_results=[],
            total_duration_ms=0,
            errors=["Playwright not available"],
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    step_results: list[StepResult] = []
    errors: list[str] = []
    total_start = datetime.now()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(DEFAULT_STEP_TIMEOUT_MS)

            for i, step in enumerate(flow.steps, 1):
                result = _execute_step(page, step, base_url, output_dir, i)
                step_results.append(result)
                if not result.passed:
                    break  # flow halts on first failure

            browser.close()
    except Exception as exc:
        errors.append(f"Playwright execution failed: {exc}")

    total_duration = int(
        (datetime.now() - total_start).total_seconds() * 1000
    )

    return build_flow_report(
        flow=flow, base_url=base_url,
        step_results=step_results, total_duration_ms=total_duration,
        errors=errors,
    )


def _execute_step(
    page, step: FlowStep, base_url: str,
    output_dir: Path, step_index: int,
) -> StepResult:
    """Execute one step against an open Playwright page."""
    start = datetime.now()
    error: str | None = None
    screenshot_path: str | None = None

    try:
        if step.action == "navigate":
            target = step.url
            if target and not target.startswith(("http://", "https://")):
                target = base_url.rstrip("/") + "/" + target.lstrip("/")
            page.goto(target, timeout=step.timeout_ms)
        elif step.action == "click":
            page.click(step.selector, timeout=step.timeout_ms)
        elif step.action == "fill":
            page.fill(step.selector, step.value, timeout=step.timeout_ms)
        elif step.action == "assert_text":
            page.wait_for_selector(
                f"text={step.value}", timeout=step.timeout_ms,
            )

        shot_path = output_dir / f"step-{step_index:02d}.png"
        page.screenshot(path=str(shot_path))
        screenshot_path = str(shot_path)
    except Exception as exc:
        error = str(exc).split("\n")[0][:200]

    duration_ms = int((datetime.now() - start).total_seconds() * 1000)
    return StepResult(
        name=step.name,
        action=step.action,
        passed=error is None,
        duration_ms=duration_ms,
        error=error,
        screenshot_path=screenshot_path,
    )
