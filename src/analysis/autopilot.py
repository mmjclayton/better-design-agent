"""
Autopilot — LLM-driven autonomous browser review.

Loop: screenshot → LLM picks next action → execute → screenshot → repeat.
When the LLM says DONE (or max_steps hit), run the standard session
synthesis over all captured pages.

Split into three layers:
  - Pure action parsing (fully testable)
  - Async browser loop (Playwright, integration-tested manually)
  - CLI wiring (reuses finalise_session)

Action vocabulary is strict: CLICK / FILL / NAVIGATE / SCROLL / DONE / STOP.
Malformed LLM responses → STOP (fail safe, preserve what was captured).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


SYSTEM_PROMPT = """\
You are an automated browser agent. You do NOT describe pages, explain
your reasoning, or write prose. You output exactly ONE action per turn
from a fixed vocabulary. Any other output is a protocol violation.

ALLOWED RESPONSES (pick exactly one per turn):

  CLICK "<visible text or CSS selector>"
  FILL "<CSS selector>" "<value>"
  NAVIGATE "<URL or relative path>"
  SCROLL "<up|down>"
  DONE
  STOP "<brief reason>"

EXAMPLES of valid responses:
  CLICK "Sign up"
  CLICK "button.primary"
  FILL "input[name=email]" "test@example.com"
  NAVIGATE "/dashboard"
  SCROLL "down"
  DONE
  STOP "no navigation element leads away from this error screen"

EXAMPLES of INVALID responses (never do these):
  "I can see this is a fitness tracking app. Let me click..."
  "Let's first explore the navigation..."
  "Action: CLICK 'Sign up'" (no "Action:" prefix)
  "CLICK Sign up" (missing quotes)

Rules:
- Your output MUST start with CLICK, FILL, NAVIGATE, SCROLL, DONE, or STOP.
- Use CLICK "<text>" matching the exact visible button/link label.
- Say DONE only when the goal is satisfied.
- Say STOP only as a last resort. ALWAYS include a brief reason in quotes.
- Never repeat the same action twice in a row.

Navigation strategy:
- The user has handled login manually before handing off to you.
- If you see a login screen, look for navigation elements (logo, menu,
  "skip", "demo" etc.) to get off it. Don't stop on login.
- Explore primary navigation first (nav bar, sidebar, tabs).
- Click into ONE representative item per section (one program, one
  exercise) — don't visit every item of the same type.
- Prefer CLICK "<visible text>" over selectors when the label is clear.
"""

USER_PROMPT_TEMPLATE = """\
GOAL: {goal}

CURRENT URL: {current_url}
STEP: {step} of {max_steps}

Page templates visited (by structural fingerprint):
{visited}

Previous actions (most recent last):
{history}

DECISION RULES (read carefully):
1. If the CURRENT PAGE marker shows a template you've visited 2+ times,
   you MUST pick an action that takes you somewhere different. Clicking
   the same top-nav buttons keeps returning you here.
2. If all visible top-level nav options lead back to templates you've
   already seen, click INTO content: program cards, table rows, list
   items, CTAs inside the main area. That opens new templates.
3. If you've visited 3+ distinct templates and the goal mentions
   specific screens you haven't found after 10 steps, say DONE — you've
   explored what's available.

Output exactly one action now. Start your response with one of:
CLICK, FILL, NAVIGATE, SCROLL, DONE, or STOP. No prose, no explanation.
"""


# ── Action model ──


VALID_VERBS = {"CLICK", "FILL", "NAVIGATE", "SCROLL", "DONE", "STOP"}


@dataclass
class AutopilotAction:
    verb: str  # one of VALID_VERBS
    target: str = ""  # selector / text / URL / direction
    value: str = ""  # for FILL

    @property
    def is_terminal(self) -> bool:
        return self.verb in {"DONE", "STOP"}

    def describe(self) -> str:
        if self.verb == "CLICK":
            return f'CLICK "{self.target}"'
        if self.verb == "FILL":
            return f'FILL "{self.target}" "{self.value}"'
        if self.verb == "NAVIGATE":
            return f'NAVIGATE "{self.target}"'
        if self.verb == "SCROLL":
            return f'SCROLL "{self.target}"'
        if self.verb == "STOP" and self.target:
            return f'STOP ({self.target})'
        return self.verb


def parse_action(llm_response: str) -> AutopilotAction:
    """Parse an LLM response into an AutopilotAction. Malformed → STOP."""
    text = llm_response.strip()
    if not text:
        return AutopilotAction(verb="STOP", target="empty response")

    # Strip common prefixes LLMs add
    text = re.sub(r"^(action|next action|i will|i'll)[:\s]+", "", text, flags=re.IGNORECASE)
    # Take first line only
    first_line = text.split("\n")[0].strip()

    # DONE / STOP (no arguments)
    upper = first_line.upper()
    if upper.startswith("DONE"):
        return AutopilotAction(verb="DONE")
    if upper.startswith("STOP"):
        return AutopilotAction(verb="STOP", target=first_line[4:].strip(' "'))

    # Extract verb + quoted arguments
    verb_match = re.match(r"^(CLICK|FILL|NAVIGATE|SCROLL)\s+", first_line, re.IGNORECASE)
    if not verb_match:
        return AutopilotAction(
            verb="STOP", target=f"unrecognised response: {first_line[:80]}"
        )
    verb = verb_match.group(1).upper()
    rest = first_line[verb_match.end():]

    # Pull out quoted strings (support both curly and straight quotes)
    quoted = re.findall(r'"([^"]*)"|\u201c([^\u201d]*)\u201d', rest)
    args = [a or b for (a, b) in quoted]

    if verb == "FILL":
        if len(args) < 2:
            return AutopilotAction(
                verb="STOP", target="FILL requires <selector> and <value>"
            )
        return AutopilotAction(verb="FILL", target=args[0], value=args[1])

    if verb == "SCROLL":
        direction = args[0].lower() if args else rest.strip().lower()
        if direction not in ("up", "down"):
            return AutopilotAction(
                verb="STOP", target=f"SCROLL needs 'up' or 'down', got '{direction}'"
            )
        return AutopilotAction(verb="SCROLL", target=direction)

    # CLICK / NAVIGATE take a single argument
    if not args:
        return AutopilotAction(
            verb="STOP", target=f"{verb} missing argument"
        )
    return AutopilotAction(verb=verb, target=args[0])


# ── Loop state + history rendering ──


@dataclass
class AutopilotState:
    goal: str
    max_steps: int = 20
    history: list[AutopilotAction] = field(default_factory=list)
    step: int = 0
    # Per-template visit tracking — the critical signal for SPAs where every
    # page has the same URL + title. Keys are structural fingerprints, values
    # are (visit_count, representative_label).
    template_visits: dict[str, tuple[int, str]] = field(default_factory=dict)
    current_template: str = ""
    _template_letter_map: dict[str, str] = field(default_factory=dict)

    @property
    def remaining_steps(self) -> int:
        return max(0, self.max_steps - self.step)

    @property
    def done(self) -> bool:
        if self.step >= self.max_steps:
            return True
        if self.history and self.history[-1].is_terminal:
            return True
        return False

    def render_history(self, tail: int = 3) -> str:
        if not self.history:
            return "(none)"
        recent = self.history[-tail:]
        return "\n".join(
            f"  {self.step - len(recent) + i + 1}. {a.describe()}"
            for i, a in enumerate(recent)
        )

    def _letter_for_template(self, fingerprint: str) -> str:
        """Assign a short letter label (A, B, C...) to each unique template."""
        if fingerprint not in self._template_letter_map:
            letter = chr(ord("A") + len(self._template_letter_map))
            # Wrap around after Z → AA, AB, ... (unlikely to hit in practice)
            if len(self._template_letter_map) >= 26:
                letter = f"T{len(self._template_letter_map)}"
            self._template_letter_map[fingerprint] = letter
        return self._template_letter_map[fingerprint]

    def render_visited(self) -> str:
        """Show Claude the template-visit distribution + current location.

        On SPAs with stable URLs/titles, the page LABEL is useless for
        differentiation but the structural fingerprint is not. Rendering
        template-level visit counts gives Claude the signal it needs to
        break out of loops: "I've been on template A four times, I need to
        find something different."
        """
        if not self.template_visits:
            return "(none yet)"
        lines: list[str] = []
        for fp, (count, label) in self.template_visits.items():
            letter = self._letter_for_template(fp)
            is_current = fp == self.current_template
            marker = " ← CURRENT PAGE" if is_current else ""
            times = "time" if count == 1 else "times"
            warning = (
                " (AVOID — visited too often)" if count >= 2 and not is_current
                else ""
            )
            lines.append(
                f"  Template {letter} ({label}): {count} {times}"
                f"{marker}{warning}"
            )
        return "\n".join(lines)

    def record_visit(self, label: str, url: str, fingerprint: str = "") -> None:
        """Record a page visit. `fingerprint` is the structural template ID.

        Increments the visit counter for this template. Keeps the first-seen
        label as the representative name.
        """
        if fingerprint:
            self.current_template = fingerprint
            if fingerprint in self.template_visits:
                count, first_label = self.template_visits[fingerprint]
                self.template_visits[fingerprint] = (count + 1, first_label)
            else:
                self.template_visits[fingerprint] = (1, label)
                self._letter_for_template(fingerprint)  # assign letter eagerly

    def is_looping(self) -> bool:
        """Detect if the last 2 actions are identical (likely loop)."""
        if len(self.history) < 2:
            return False
        return (
            self.history[-1].describe() == self.history[-2].describe()
            and not self.history[-1].is_terminal
        )

    def is_stuck_on_current_template(self, threshold: int = 4) -> bool:
        """Hard stop signal: current template has been visited N+ times."""
        if not self.current_template:
            return False
        count, _ = self.template_visits.get(self.current_template, (0, ""))
        return count >= threshold


def build_user_prompt(state: AutopilotState, current_url: str) -> str:
    return USER_PROMPT_TEMPLATE.format(
        goal=state.goal,
        current_url=current_url,
        step=state.step + 1,
        max_steps=state.max_steps,
        history=state.render_history(),
        visited=state.render_visited(),
    )


# ── Action execution (Playwright) ──


async def execute_action(page, action: AutopilotAction, base_url: str) -> tuple[bool, str]:
    """Run the action in Playwright. Returns (success, message).

    Every successful interaction is followed by a page-settle wait so the
    LLM's next screenshot reflects the real post-action state.
    """
    try:
        if action.verb == "CLICK":
            result = await _do_click(page, action.target)
        elif action.verb == "FILL":
            result = await _do_fill(page, action.target, action.value)
        elif action.verb == "NAVIGATE":
            result = await _do_navigate(page, action.target, base_url)
        elif action.verb == "SCROLL":
            result = await _do_scroll(page, action.target)
        else:
            return True, f"{action.verb} completed"

        # If the interaction succeeded, wait for the page to settle so the
        # next screenshot captures the actual post-action state.
        if result[0]:
            await _wait_for_settle(page)
        return result
    except Exception as exc:
        return False, f"{action.verb} failed: {str(exc)[:150]}"


def _looks_like_selector(target: str) -> bool:
    """True if `target` looks like a CSS selector rather than visible text."""
    if not target:
        return False
    if target.startswith((".", "#", "[", "*", ":")):
        return True
    # Tag-first selectors: "button.x", "button[type=submit]", "button#id", "input"
    if target[0].isalpha():
        # Look for selector-characteristic punctuation in the first 20 chars
        prefix = target[:20]
        return any(c in prefix for c in (".", "#", "[", ">"))
    return False


async def _click_locator(page, locator, label: str) -> tuple[bool, str]:
    """Attempt a normal click, fall back to force=True if actionability fails.

    Playwright's default click runs an actionability check: element must be
    visible, stable, enabled, receiving pointer events. SPAs with overlay
    layers or `pointer-events: none` containers often fail this. Force click
    bypasses the check and dispatches the event directly.
    """
    count = await locator.count()
    if count == 0:
        return False, f"no element matched {label}"

    # Scroll into view first — helps with elements below the fold.
    try:
        await locator.scroll_into_view_if_needed(timeout=3_000)
    except Exception:
        pass

    # Standard click (respects actionability).
    try:
        await locator.click(timeout=5_000)
        return True, f"clicked {label}"
    except Exception as exc_standard:
        # Standard click failed actionability — fall back to force click.
        try:
            await locator.click(timeout=3_000, force=True)
            return True, f"clicked {label} (force)"
        except Exception as exc_force:
            # Last resort: dispatch the event directly via JS.
            try:
                await locator.dispatch_event("click", timeout=3_000)
                return True, f"clicked {label} (dispatch)"
            except Exception:
                return False, (
                    f"{label} not clickable: {str(exc_standard)[:80]}"
                )


async def _do_click(page, target: str) -> tuple[bool, str]:
    """Click by selector OR visible text. Prefers role-based locators for text."""
    if _looks_like_selector(target):
        loc = page.locator(target).first
        return await _click_locator(page, loc, f"selector `{target}`")

    # Text-based click. Try role-based locators first (button, link, tab, menuitem)
    # — they filter to actual interactive elements.
    for role in ("button", "link", "tab", "menuitem"):
        try:
            loc = page.get_by_role(role, name=target, exact=False).first
            if await loc.count() > 0:
                return await _click_locator(page, loc, f'{role} "{target}"')
        except Exception:
            continue

    # Fallback: Playwright's text= locator, filtered to the smallest matching element.
    loc = page.get_by_text(target, exact=False).first
    return await _click_locator(page, loc, f'text "{target}"')


async def _do_fill(page, selector: str, value: str) -> tuple[bool, str]:
    # Wait for the input to be visible before filling.
    try:
        await page.wait_for_selector(selector, state="visible", timeout=10_000)
    except Exception:
        pass  # try the fill anyway — Playwright's own wait may catch it
    await page.fill(selector, value, timeout=10_000)
    return True, f"filled `{selector}`"


async def _do_navigate(page, target: str, base_url: str) -> tuple[bool, str]:
    if not target.startswith(("http://", "https://")):
        target = base_url.rstrip("/") + "/" + target.lstrip("/")
    await page.goto(target, wait_until="domcontentloaded", timeout=30_000)
    return True, f"navigated to {target}"


async def _do_scroll(page, direction: str) -> tuple[bool, str]:
    delta = 600 if direction == "down" else -600
    await page.evaluate(f"window.scrollBy(0, {delta})")
    return True, f"scrolled {direction}"


async def _wait_for_settle(page, max_ms: int = 2500) -> None:
    """Wait for the page to settle after an interaction.

    SPAs often render new content asynchronously after a click/fill. Without
    this wait, the next screenshot can show the pre-interaction state,
    confusing the LLM into repeating its last action.

    Waits for: `domcontentloaded` (cheap), then network-idle with a short
    cap (SPAs often never reach true network idle). Total cap is ~max_ms.
    """
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=max_ms)
    except Exception:
        pass
    try:
        await page.wait_for_load_state("networkidle", timeout=max_ms)
    except Exception:
        # Network never idles on apps with polling / websockets — that's fine.
        pass


# ── Action log rendering ──


@dataclass
class ActionLogEntry:
    step: int
    url_before: str
    action: AutopilotAction
    success: bool
    message: str


def render_action_log(entries: list[ActionLogEntry], goal: str) -> str:
    lines = [
        "# Autopilot action log",
        "",
        f"**Goal:** {goal}",
        f"**Steps taken:** {len(entries)}",
        "",
        "| # | URL before | Action | Result |",
        "|---|-----------|--------|--------|",
    ]
    for e in entries:
        status = "PASS" if e.success else "FAIL"
        action_desc = e.action.describe()
        lines.append(
            f"| {e.step} | `{e.url_before}` | `{action_desc}` | {status}: {e.message[:60]} |"
        )
    return "\n".join(lines)


# ── LLM provider wrapper ──


def _default_handoff_prompt() -> str:
    """Blocking prompt waiting for the user to hand off to autopilot."""
    return input("\n  Ready? Press Enter to start (or 'q' to cancel): ")


def default_action_provider(
    screenshot_path: str, system_prompt: str, user_prompt: str,
) -> str:
    """Call the configured LLM with a screenshot and return the response text."""
    from src.providers.llm import call_llm
    return call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        image_path=screenshot_path,
        max_tokens=200,
        temperature=0.1,  # Low — we want deterministic action choices.
    )


# ── Main autopilot loop ──


async def run_autopilot_session(
    start_url: str,
    goal: str,
    mode: str = "pragmatic-audit",
    max_steps: int = 20,
    viewport_width: int = 1440,
    viewport_height: int = 900,
    output_dir: Path | None = None,
    action_provider=None,
    handoff_fn=None,
) -> tuple[list, list[ActionLogEntry]]:
    """Run the autopilot loop. Returns (captures, action_log_entries).

    `handoff_fn` is called after the browser opens + initial navigation, so
    the user can log in / navigate manually before Claude takes over.
    Defaults to a blocking `input()` prompt. Injected for testability.
    """
    import asyncio as _asyncio
    from playwright.async_api import async_playwright
    from datetime import datetime
    from src.analysis.interactive_session import (
        CaptureResult, derive_page_label, _capture_current_page, _run_analysis,
    )

    if action_provider is None:
        action_provider = default_action_provider
    if handoff_fn is None:
        handoff_fn = _default_handoff_prompt

    if output_dir is None:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = Path("output") / f"autopilot-{ts}"
    output_dir.mkdir(parents=True, exist_ok=True)

    state = AutopilotState(goal=goal, max_steps=max_steps)
    captures: list = []
    action_log: list[ActionLogEntry] = []
    captured_fingerprints: set[str] = set()

    from src.analysis.structural_fingerprint import structural_fingerprint

    def _flush_session_files() -> None:
        """Write actions.md + session synthesis after every step.

        Means Ctrl-C mid-run still leaves usable artefacts on disk.
        """
        try:
            (output_dir / "actions.md").write_text(
                render_action_log(action_log, goal)
            )
            if captures:
                from src.analysis.interactive_session import finalise_session
                finalise_session(captures, output_dir, mode)
        except Exception:
            pass  # never let a flush failure crash the loop

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": viewport_width, "height": viewport_height},
            locale="en-AU",
        )
        page = await context.new_page()

        try:
            await page.goto(start_url, wait_until="domcontentloaded", timeout=30_000)
        except Exception as exc:
            print(f"Warning: initial navigation failed: {exc}")

        # Hand off to the user — if the app needs login, they do it manually
        # in this browser window, THEN press Enter, THEN Claude takes over.
        print(
            "\n"
            "──────────────────────────────────────────────────────────\n"
            "  Browser is open. If your app needs login:\n"
            "    1. Log in manually in the browser window\n"
            "    2. Navigate to where you want me to start from\n"
            "    3. Come back here and press Enter\n"
            "  Or press Enter now if the app is already ready.\n"
            "──────────────────────────────────────────────────────────"
        )
        try:
            response = await _asyncio.to_thread(handoff_fn)
            if response.strip().lower() in {"q", "quit", "exit"}:
                print("Cancelled before start.")
                await browser.close()
                return captures, action_log
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            await browser.close()
            return captures, action_log

        current_url_after_handoff = page.url
        print(f"\n[autopilot] Starting at {current_url_after_handoff}")
        print(f"[autopilot] Goal: {goal}")
        print(f"[autopilot] Max steps: {max_steps}\n")

        while not state.done:
            state.step += 1
            current_url = page.url
            print(f"\n[step {state.step}] at {current_url}")

            # Capture current state (for both the LLM and the review record)
            capture_index = len(captures) + 1
            print("  → capturing page...", end="", flush=True)
            try:
                shot, text, dom_data = await _capture_current_page(
                    page, output_dir, capture_index,
                )
                print(" done")
            except Exception as exc:
                print(f"\n  Capture failed: {exc}")
                state.history.append(AutopilotAction(
                    verb="STOP", target=f"capture failed: {exc}"
                ))
                break

            # Label + fingerprint + record visit. Fingerprint is the key
            # signal for SPAs — label alone collapses to the site name.
            label = derive_page_label(dom_data, capture_index)
            fp = structural_fingerprint(dom_data)
            state.record_visit(label, current_url, fingerprint=fp)
            template_letter = state._letter_for_template(fp)
            visit_count = state.template_visits[fp][0]
            print(
                f"  → labelled as: {label} "
                f"(template {template_letter}, visit #{visit_count})"
            )

            # Structural dedup: if this page's template matches one we've
            # already captured, skip the analysis + save. Claude still sees
            # the screenshot to decide what to navigate to next.
            if fp in captured_fingerprints:
                print(
                    "  → same template as a page I've already captured, "
                    "skipping analysis + save"
                )
            else:
                captured_fingerprints.add(fp)
                print("  → running quick audit (no AI)...", end="", flush=True)
                _analysis_start = datetime.now()
                try:
                    report_md = await _asyncio.wait_for(
                        _asyncio.to_thread(
                            _run_analysis, "pragmatic-audit",
                            dom_data, text, current_url, shot,
                        ),
                        timeout=20.0,
                    )
                    _elapsed = (datetime.now() - _analysis_start).total_seconds()
                    print(f" done ({_elapsed:.1f}s)")
                except _asyncio.TimeoutError:
                    print("\n  ✗ Analysis timed out after 20s on this page.")
                    report_md = (
                        "_Analysis timed out — skipping to navigation._"
                    )
                except Exception as exc:
                    print(f"\n  Analysis failed: {exc}")
                    report_md = f"_Analysis failed: {exc}_"

                captures.append(CaptureResult(
                    index=capture_index, url=current_url, label=label,
                    screenshot_path=shot, report_markdown=report_md, mode=mode,
                ))
                (output_dir / f"capture-{capture_index:02d}.md").write_text(report_md)

            # Flush session files after every step so Ctrl-C doesn't lose progress.
            _flush_session_files()

            # Detect loops: identical action twice in a row → force STOP
            if state.is_looping():
                print("  Detected action loop — stopping.")
                state.history.append(AutopilotAction(
                    verb="STOP", target="action loop detected"
                ))
                break

            # Detect template-thrashing: same template visited 4+ times
            # means Claude is orbiting without making progress. Stop so
            # the session still produces useful output.
            if state.is_stuck_on_current_template(threshold=4):
                current_count = state.template_visits[state.current_template][0]
                print(
                    f"  Stuck on template {template_letter} "
                    f"(visit #{current_count}) — stopping to preserve output."
                )
                state.history.append(AutopilotAction(
                    verb="STOP",
                    target=f"stuck on template {template_letter} after {current_count} visits",
                ))
                break

            # Ask the LLM for the next action (off the main thread so the
            # browser stays responsive while we wait for the vision model).
            # Hard 90s timeout — if the API stalls, we fail fast instead of
            # hanging forever.
            shot_size_kb = Path(shot).stat().st_size // 1024
            from src.config import settings as _llm_settings
            print(
                f"  → asking {_llm_settings.llm_model} "
                f"(screenshot {shot_size_kb} KB, 15-60s typical, 90s timeout)...",
                end="", flush=True,
            )
            user_prompt = build_user_prompt(state, current_url)
            _llm_start = datetime.now()
            try:
                response = await _asyncio.wait_for(
                    _asyncio.to_thread(
                        action_provider, shot, SYSTEM_PROMPT, user_prompt,
                    ),
                    timeout=90.0,
                )
                _elapsed = (datetime.now() - _llm_start).total_seconds()
                print(f" done ({_elapsed:.1f}s)")
            except _asyncio.TimeoutError:
                _elapsed = (datetime.now() - _llm_start).total_seconds()
                print(f"\n  ✗ LLM call timed out after {_elapsed:.0f}s. Stopping.")
                print(f"    Model: {_llm_settings.llm_model}")
                print(
                    "    Try a different model via LLM_MODEL in .env, "
                    "or check API key + credit."
                )
                state.history.append(AutopilotAction(
                    verb="STOP", target=f"LLM timeout after {_elapsed:.0f}s"
                ))
                break
            except Exception as exc:
                print(f"\n  ✗ LLM call failed: {exc}")
                state.history.append(AutopilotAction(
                    verb="STOP", target=f"LLM error: {str(exc)[:80]}"
                ))
                break

            action = parse_action(response)
            state.history.append(action)
            print(f"  Claude said: {response.strip()[:160]}")
            print(f"  Action: {action.describe()}")

            if action.is_terminal:
                action_log.append(ActionLogEntry(
                    step=state.step, url_before=current_url,
                    action=action, success=True,
                    message=f"terminal: {action.describe()}",
                ))
                if action.verb == "STOP":
                    print(f"\n  Claude stopped. Reason: {action.target or '(no reason given)'}")
                    print(
                        "  Tip: if this was the wrong moment to stop, try a more "
                        "specific goal or navigate to the starting page yourself "
                        "before pressing Enter."
                    )
                else:
                    print(f"  → {action.verb}")
                break

            # Execute the action
            print("  → executing...", end="", flush=True)
            success, message = await execute_action(page, action, start_url)
            print()
            action_log.append(ActionLogEntry(
                step=state.step, url_before=current_url,
                action=action, success=success, message=message,
            ))
            print(f"  {'✓' if success else '✗'} {message}")
            _flush_session_files()

            if not success:
                # Tell the LLM next turn, don't auto-stop after one failure.
                # But three consecutive failures → stop.
                recent_failures = sum(
                    1 for e in action_log[-3:] if not e.success
                )
                if recent_failures >= 3:
                    print("  Three consecutive failures — stopping.")
                    break

        try:
            await browser.close()
        except Exception:
            pass

    return captures, action_log


def run_autopilot_sync(start_url: str, goal: str, **kwargs):
    """Sync wrapper around the async autopilot loop."""
    import asyncio
    return asyncio.run(run_autopilot_session(start_url, goal, **kwargs))
