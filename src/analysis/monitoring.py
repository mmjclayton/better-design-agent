"""
Scheduled-monitoring report builder.

Given a current WCAG report, DOM data, and a slice of history, assemble a
trend-aware monitoring report and decide whether to fire an alert. Scheduling
is the caller's problem — this module is purely a stateless report builder.

Alerting is fire-and-forget: a Slack-compatible HTTP POST. Webhook failures
are logged in the report and never crash the caller.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from src.analysis.ci_runner import (
    ViolationFingerprint,
    _fingerprint_axe_violations,
    _fingerprint_wcag_violations,
)
from src.analysis.diff_analyzer import diff_fingerprints
from src.analysis.history import RunRecord


SCHEMA_VERSION = 1

EXIT_STABLE = 0
EXIT_REGRESSION = 1
EXIT_TECHNICAL_ERROR = 2

DEFAULT_TREND_WINDOW = 10
DEFAULT_SCORE_TOLERANCE = 2.0  # pp — matches CI gate default
DEFAULT_SEVERITY_FLOOR = "serious"
WEBHOOK_TIMEOUT_SECONDS = 5.0


@dataclass
class TrendPoint:
    timestamp: str
    score: float

    def to_dict(self) -> dict:
        return {"timestamp": self.timestamp, "score": self.score}


@dataclass
class MonitorReport:
    schema_version: int
    url: str
    timestamp: str
    score: float
    score_previous: float | None
    score_delta: float | None
    trend: list[TrendPoint]
    new_violations: list[dict]
    fixed_violations: list[dict]
    alert_fired: bool
    alert_payload: dict | None
    alert_error: str | None
    exit_code: int
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "url": self.url,
            "timestamp": self.timestamp,
            "score": self.score,
            "score_previous": self.score_previous,
            "score_delta": self.score_delta,
            "trend": [t.to_dict() for t in self.trend],
            "new_violations": self.new_violations,
            "fixed_violations": self.fixed_violations,
            "alert_fired": self.alert_fired,
            "alert_payload": self.alert_payload,
            "alert_error": self.alert_error,
            "exit_code": self.exit_code,
            "errors": self.errors,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_markdown(self) -> str:
        lines = [
            f"# Monitoring Report — {self.url}",
            "",
            f"**Checked at:** {self.timestamp}",
            "",
        ]

        if self.errors:
            lines.append("## Errors")
            for e in self.errors:
                lines.append(f"- {e}")
            lines.append("")

        # Score
        lines.append("## Score")
        lines.append("")
        if self.score_previous is not None:
            sign = "+" if (self.score_delta or 0) >= 0 else ""
            lines.append(
                f"**WCAG:** {self.score_previous}% → **{self.score}%** "
                f"({sign}{self.score_delta}pp)"
            )
        else:
            lines.append(f"**WCAG:** {self.score}% (no previous run)")
        lines.append("")

        # Regression callouts
        if self.new_violations:
            lines.append(
                f"## Regressions ({len(self.new_violations)} new violation(s))"
            )
            lines.append("")
            for v in self.new_violations[:10]:
                lines.append(
                    f"- **{v.get('criterion', '?')}** "
                    f"`{v.get('element', '')}` "
                    f"— {v.get('issue', '')[:80]}"
                )
            if len(self.new_violations) > 10:
                lines.append(f"- … +{len(self.new_violations) - 10} more")
            lines.append("")

        # Improvements
        if self.fixed_violations:
            lines.append(
                f"## Improvements ({len(self.fixed_violations)} fixed)"
            )
            lines.append("")

        # Trend table
        if self.trend:
            lines.append("## Trend")
            lines.append("")
            lines.append("| Timestamp | Score |")
            lines.append("|-----------|-------|")
            for point in self.trend:
                lines.append(f"| {point.timestamp} | {point.score}% |")
            lines.append("")

        # Alert status
        if self.alert_payload is not None:
            lines.append("## Alert")
            lines.append("")
            if self.alert_fired:
                lines.append("- **Fired** — webhook posted successfully.")
            elif self.alert_error:
                lines.append(f"- **Not fired** — webhook call failed: `{self.alert_error}`")
            else:
                lines.append("- **Not fired** — no regression to report.")
            lines.append("")

        lines.append(f"**Exit code:** {self.exit_code}")
        return "\n".join(lines)


# ── Helpers ──


def _fingerprints_now(wcag_report, dom_data: dict) -> list[ViolationFingerprint]:
    severity_gate = {"critical", "serious"}
    fps = _fingerprint_wcag_violations(wcag_report) if wcag_report else []
    fps += _fingerprint_axe_violations(dom_data or {}, severity_gate)
    return fps


def _fingerprints_from_run(run: RunRecord) -> list[ViolationFingerprint]:
    return [
        ViolationFingerprint(
            criterion=str(issue.get("criterion", "")),
            element=str(issue.get("element", "")),
            issue=str(issue.get("details", issue.get("issue", ""))),
        )
        for issue in (run.issues or [])
    ]


def _build_trend(history: list[RunRecord], window: int) -> list[TrendPoint]:
    if window <= 0:
        return []
    truncated = history[-window:]
    return [
        TrendPoint(timestamp=r.timestamp, score=r.wcag_score)
        for r in truncated
    ]


def _format_alert_text(
    url: str,
    score: float,
    score_delta: float | None,
    new_count: int,
) -> str:
    parts = [f"design-intel: regression on {url}"]
    if score_delta is not None:
        sign = "+" if score_delta >= 0 else ""
        parts.append(f"score {score}% ({sign}{score_delta}pp)")
    if new_count > 0:
        parts.append(f"{new_count} new critical/serious violation(s)")
    return " — ".join(parts)


def post_to_webhook(webhook_url: str, payload: dict) -> tuple[bool, str | None]:
    """Fire-and-forget POST. Returns (success, error_message_or_none)."""
    try:
        resp = httpx.post(
            webhook_url, json=payload, timeout=WEBHOOK_TIMEOUT_SECONDS,
        )
        if 200 <= resp.status_code < 300:
            return True, None
        return False, f"HTTP {resp.status_code}"
    except Exception as exc:
        return False, str(exc)


# ── Main entry ──


def build_monitor_report(
    *,
    url: str,
    wcag_report,
    dom_data: dict,
    history: list[RunRecord],
    previous_run: RunRecord | None,
    trend_window: int = DEFAULT_TREND_WINDOW,
    score_tolerance: float = DEFAULT_SCORE_TOLERANCE,
    alert_webhook: str | None = None,
    errors: list[str] | None = None,
    now: datetime | None = None,
    webhook_poster=post_to_webhook,
) -> MonitorReport:
    """Build a MonitorReport from a fresh audit and optional history."""
    errs = list(errors or [])
    timestamp = (now or datetime.now()).isoformat(timespec="seconds")

    score = wcag_report.score_percentage if wcag_report else 0.0
    score_previous = previous_run.wcag_score if previous_run else None
    score_delta = (
        round(score - score_previous, 1) if score_previous is not None else None
    )

    # Fingerprint diff vs previous run
    current_fps = _fingerprints_now(wcag_report, dom_data)
    previous_fps = _fingerprints_from_run(previous_run) if previous_run else []
    issue_diff = diff_fingerprints(previous_fps, current_fps)

    trend = _build_trend(history, trend_window)

    # Regression decision — same rules as the CI gate.
    new_count = len(issue_diff.new)
    score_regressed = (
        score_delta is not None and score_delta < -score_tolerance
    )
    is_regression = new_count > 0 or score_regressed

    # Exit code
    if errs:
        exit_code = EXIT_TECHNICAL_ERROR
    elif is_regression:
        exit_code = EXIT_REGRESSION
    else:
        exit_code = EXIT_STABLE

    # Alerting
    alert_payload: dict | None = None
    alert_fired = False
    alert_error: str | None = None
    if alert_webhook:
        text = _format_alert_text(url, score, score_delta, new_count)
        alert_payload = {"text": text}
        if is_regression:
            alert_fired, alert_error = webhook_poster(alert_webhook, alert_payload)

    return MonitorReport(
        schema_version=SCHEMA_VERSION,
        url=url,
        timestamp=timestamp,
        score=score,
        score_previous=score_previous,
        score_delta=score_delta,
        trend=trend,
        new_violations=issue_diff.new,
        fixed_violations=issue_diff.fixed,
        alert_fired=alert_fired,
        alert_payload=alert_payload,
        alert_error=alert_error,
        exit_code=exit_code,
        errors=errs,
    )
