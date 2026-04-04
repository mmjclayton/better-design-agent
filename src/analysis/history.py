"""
Regression tracking for design-intel.

Stores run results as JSON in .design-intel/ directory within the target
project. Compares current run to previous runs to show what improved,
what regressed, and what's new.
"""

import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict


HISTORY_DIR_NAME = ".design-intel"


@dataclass
class RunIssue:
    """A single issue found in a run."""
    criterion: str
    severity: int  # 0-4
    element: str = ""
    details: str = ""
    status: str = ""  # fail, warning, pass

    @property
    def key(self) -> str:
        """Stable key for comparing issues across runs."""
        return f"{self.criterion}|{self.element}"


@dataclass
class RunRecord:
    """Complete record of a single design-intel run."""
    timestamp: str
    url: str
    device: str
    pages_crawled: int
    score: int
    score_max: int = 100
    wcag_score: float = 0.0
    wcag_pass: int = 0
    wcag_fail: int = 0
    wcag_warning: int = 0
    total_violations: int = 0
    issues: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RunRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class RegressionDiff:
    """Diff between two runs."""
    previous: RunRecord
    current: RunRecord
    fixed: list[dict] = field(default_factory=list)
    new_issues: list[dict] = field(default_factory=list)
    persistent: list[dict] = field(default_factory=list)
    score_delta: int = 0
    wcag_delta: float = 0.0

    def to_markdown(self) -> str:
        lines = [
            "## Regression Report\n",
            f"**Previous run:** {self.previous.timestamp} | Score: {self.previous.score}/100 | WCAG: {self.previous.wcag_score}%",
            f"**Current run:** {self.current.timestamp} | Score: {self.current.score}/100 | WCAG: {self.current.wcag_score}%",
            "",
        ]

        # Score change
        if self.score_delta > 0:
            lines.append(f"**Score: +{self.score_delta} points** (improved)")
        elif self.score_delta < 0:
            lines.append(f"**Score: {self.score_delta} points** (regressed)")
        else:
            lines.append("**Score: unchanged**")

        if self.wcag_delta > 0:
            lines.append(f"**WCAG: +{self.wcag_delta}%** (improved)")
        elif self.wcag_delta < 0:
            lines.append(f"**WCAG: {self.wcag_delta}%** (regressed)")

        lines.append("")

        # Fixed issues
        if self.fixed:
            lines.append(f"### Fixed ({len(self.fixed)} issues resolved)\n")
            for issue in self.fixed:
                lines.append(f"- ~~{issue.get('criterion', '?')}: {issue.get('details', '')[:80]}~~")
            lines.append("")

        # New issues
        if self.new_issues:
            lines.append(f"### New Issues ({len(self.new_issues)} introduced)\n")
            for issue in self.new_issues:
                lines.append(f"- **{issue.get('criterion', '?')}**: {issue.get('details', '')[:80]}")
            lines.append("")

        # Persistent
        if self.persistent:
            lines.append(f"### Persistent ({len(self.persistent)} unresolved)\n")
            for issue in self.persistent:
                lines.append(f"- {issue.get('criterion', '?')}: {issue.get('details', '')[:80]}")
            lines.append("")

        if not self.fixed and not self.new_issues:
            lines.append("No changes detected between runs.\n")

        return "\n".join(lines)


def _get_history_dir(url: str) -> Path:
    """Get or create the history directory for a project."""
    # Store in the current working directory
    history_dir = Path.cwd() / HISTORY_DIR_NAME
    history_dir.mkdir(exist_ok=True)
    return history_dir


def _get_history_file(url: str) -> Path:
    """Get the history file path for a URL."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.hostname or "unknown"
    port = parsed.port or ""
    safe_name = f"{host}_{port}".rstrip("_").replace(".", "-")
    return _get_history_dir(url) / f"{safe_name}.json"


def save_run(record: RunRecord) -> Path:
    """Save a run record to history."""
    history_file = _get_history_file(record.url)

    # Load existing history
    runs = []
    if history_file.exists():
        try:
            runs = json.loads(history_file.read_text())
        except (json.JSONDecodeError, KeyError):
            runs = []

    runs.append(record.to_dict())

    # Keep last 50 runs
    runs = runs[-50:]

    history_file.write_text(json.dumps(runs, indent=2))
    return history_file


def load_history(url: str) -> list[RunRecord]:
    """Load run history for a URL."""
    history_file = _get_history_file(url)
    if not history_file.exists():
        return []

    try:
        runs = json.loads(history_file.read_text())
        return [RunRecord.from_dict(r) for r in runs]
    except (json.JSONDecodeError, KeyError):
        return []


def get_previous_run(url: str) -> RunRecord | None:
    """Get the most recent previous run for a URL."""
    history = load_history(url)
    return history[-1] if history else None


def compute_diff(previous: RunRecord, current: RunRecord) -> RegressionDiff:
    """Compare two runs and produce a regression diff."""
    diff = RegressionDiff(
        previous=previous,
        current=current,
        score_delta=current.score - previous.score,
        wcag_delta=round(current.wcag_score - previous.wcag_score, 1),
    )

    # Build issue maps by stable key
    prev_issues = {f"{i.get('criterion', '')}|{i.get('element', '')}": i for i in previous.issues}
    curr_issues = {f"{i.get('criterion', '')}|{i.get('element', '')}": i for i in current.issues}

    prev_keys = set(prev_issues.keys())
    curr_keys = set(curr_issues.keys())

    # Fixed: was in previous, not in current
    for key in prev_keys - curr_keys:
        diff.fixed.append(prev_issues[key])

    # New: in current, not in previous
    for key in curr_keys - prev_keys:
        diff.new_issues.append(curr_issues[key])

    # Persistent: in both
    for key in prev_keys & curr_keys:
        diff.persistent.append(curr_issues[key])

    return diff


def build_run_record(
    url: str,
    device: str,
    pages_crawled: int,
    score: int,
    wcag_report,
    issues: list[dict] | None = None,
) -> RunRecord:
    """Build a RunRecord from critique results."""
    return RunRecord(
        timestamp=datetime.now().isoformat(timespec="seconds"),
        url=url,
        device=device,
        pages_crawled=pages_crawled,
        score=score,
        wcag_score=wcag_report.score_percentage if wcag_report else 0.0,
        wcag_pass=wcag_report.pass_count if wcag_report else 0,
        wcag_fail=wcag_report.fail_count if wcag_report else 0,
        wcag_warning=wcag_report.warning_count if wcag_report else 0,
        total_violations=wcag_report.total_violations if wcag_report else 0,
        issues=issues or [r.to_dict() if hasattr(r, 'to_dict') else {"criterion": r.criterion, "status": r.status, "details": r.details, "element": "", "count": r.count} for r in (wcag_report.results if wcag_report else []) if r.status == "fail"],
    )
