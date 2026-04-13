"""Tests for autopilot's pure layer (action parsing + state)."""

from src.analysis.autopilot import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    VALID_VERBS,
    ActionLogEntry,
    AutopilotAction,
    AutopilotState,
    build_user_prompt,
    parse_action,
    render_action_log,
)


# ── Parse action — valid verbs ──


def test_parse_click_with_quoted_text():
    action = parse_action('CLICK "Sign up"')
    assert action.verb == "CLICK"
    assert action.target == "Sign up"


def test_parse_click_with_selector():
    action = parse_action('CLICK "button.primary"')
    assert action.verb == "CLICK"
    assert action.target == "button.primary"


def test_parse_fill_two_quoted_args():
    action = parse_action('FILL "input[name=email]" "test@example.com"')
    assert action.verb == "FILL"
    assert action.target == "input[name=email]"
    assert action.value == "test@example.com"


def test_parse_navigate_with_url():
    action = parse_action('NAVIGATE "/dashboard"')
    assert action.verb == "NAVIGATE"
    assert action.target == "/dashboard"


def test_parse_scroll_down():
    action = parse_action('SCROLL "down"')
    assert action.verb == "SCROLL"
    assert action.target == "down"


def test_parse_scroll_up():
    action = parse_action('SCROLL "up"')
    assert action.verb == "SCROLL"
    assert action.target == "up"


def test_parse_done_no_args():
    action = parse_action("DONE")
    assert action.verb == "DONE"


def test_parse_stop_no_args():
    action = parse_action("STOP")
    assert action.verb == "STOP"


# ── Verb case insensitivity ──


def test_parse_click_lowercase():
    action = parse_action('click "Sign in"')
    assert action.verb == "CLICK"
    assert action.target == "Sign in"


# ── Curly quotes ──


def test_parse_handles_curly_quotes():
    action = parse_action('CLICK \u201cSign up\u201d')
    assert action.verb == "CLICK"
    assert action.target == "Sign up"


# ── Common LLM prefixes ──


def test_parse_strips_action_prefix():
    action = parse_action('Action: CLICK "Go"')
    assert action.verb == "CLICK"
    assert action.target == "Go"


def test_parse_strips_next_action_prefix():
    action = parse_action('Next action: NAVIGATE "/signup"')
    assert action.verb == "NAVIGATE"
    assert action.target == "/signup"


def test_parse_strips_i_will_prefix():
    action = parse_action("I will CLICK \"Submit\"")
    assert action.verb == "CLICK"
    assert action.target == "Submit"


# ── Malformed → STOP (fail safe) ──


def test_parse_empty_string_stops():
    action = parse_action("")
    assert action.verb == "STOP"


def test_parse_gibberish_stops():
    action = parse_action("banana smoothie time")
    assert action.verb == "STOP"
    assert "unrecognised" in action.target.lower()


def test_parse_click_without_quoted_arg_stops():
    action = parse_action("CLICK Sign up")
    # No quotes → no args → STOP
    assert action.verb == "STOP"


def test_parse_fill_missing_value_stops():
    action = parse_action('FILL "input.email"')
    assert action.verb == "STOP"
    assert "FILL requires" in action.target


def test_parse_scroll_bad_direction_stops():
    action = parse_action('SCROLL "sideways"')
    assert action.verb == "STOP"
    assert "needs 'up' or 'down'" in action.target


# ── Multiline — takes first line only ──


def test_parse_multiline_uses_first():
    action = parse_action('CLICK "Sign up"\nThen we\'ll wait.')
    assert action.verb == "CLICK"
    assert action.target == "Sign up"


# ── Action.describe() round-trip ──


def test_describe_click():
    assert AutopilotAction("CLICK", target="Sign up").describe() == 'CLICK "Sign up"'


def test_describe_fill():
    assert AutopilotAction("FILL", target="input", value="test").describe() == 'FILL "input" "test"'


def test_describe_done_and_stop_no_args():
    assert AutopilotAction("DONE").describe() == "DONE"
    assert AutopilotAction("STOP").describe() == "STOP"


def test_action_is_terminal():
    assert AutopilotAction("DONE").is_terminal
    assert AutopilotAction("STOP").is_terminal
    assert not AutopilotAction("CLICK", target="x").is_terminal


# ── State ──


def test_state_done_when_max_steps_reached():
    state = AutopilotState(goal="x", max_steps=5, step=5)
    assert state.done


def test_state_done_when_terminal_action_in_history():
    state = AutopilotState(goal="x", max_steps=10)
    state.history.append(AutopilotAction("DONE"))
    assert state.done


def test_state_not_done_when_more_steps_available():
    state = AutopilotState(goal="x", max_steps=10, step=3)
    state.history.append(AutopilotAction("CLICK", target="a"))
    assert not state.done


def test_state_remaining_steps():
    state = AutopilotState(goal="x", max_steps=10, step=3)
    assert state.remaining_steps == 7


def test_state_remaining_never_negative():
    state = AutopilotState(goal="x", max_steps=5, step=10)
    assert state.remaining_steps == 0


def test_render_history_empty():
    state = AutopilotState(goal="x")
    assert state.render_history() == "(none)"


def test_render_history_tail():
    state = AutopilotState(goal="x", step=5)
    for i in range(5):
        state.history.append(AutopilotAction("CLICK", target=f"item-{i}"))
    rendered = state.render_history(tail=3)
    # Shows last 3 only
    assert "item-2" in rendered
    assert "item-3" in rendered
    assert "item-4" in rendered
    assert "item-0" not in rendered


def test_is_looping_detects_repeat():
    state = AutopilotState(goal="x")
    state.history.append(AutopilotAction("CLICK", target="same"))
    state.history.append(AutopilotAction("CLICK", target="same"))
    assert state.is_looping()


def test_is_looping_ignores_different_actions():
    state = AutopilotState(goal="x")
    state.history.append(AutopilotAction("CLICK", target="a"))
    state.history.append(AutopilotAction("CLICK", target="b"))
    assert not state.is_looping()


def test_is_looping_ignores_terminal_actions():
    state = AutopilotState(goal="x")
    state.history.append(AutopilotAction("STOP"))
    state.history.append(AutopilotAction("STOP"))
    assert not state.is_looping()


def test_is_looping_requires_two_entries():
    state = AutopilotState(goal="x")
    state.history.append(AutopilotAction("CLICK", target="a"))
    assert not state.is_looping()


# ── Template tracking ──


def test_record_visit_tracks_first_label():
    state = AutopilotState(goal="x")
    state.record_visit("Dashboard", "https://x.com/", fingerprint="fp-a")
    state.record_visit("DifferentLabel", "https://x.com/", fingerprint="fp-a")
    count, first = state.template_visits["fp-a"]
    assert count == 2
    assert first == "Dashboard"  # keeps first-seen label


def test_record_visit_increments_count():
    state = AutopilotState(goal="x")
    for _ in range(5):
        state.record_visit("Home", "https://x.com/", fingerprint="fp-a")
    assert state.template_visits["fp-a"][0] == 5


def test_record_visit_distinct_templates():
    state = AutopilotState(goal="x")
    state.record_visit("Home", "https://x.com/", fingerprint="fp-a")
    state.record_visit("List", "https://x.com/", fingerprint="fp-b")
    state.record_visit("Detail", "https://x.com/", fingerprint="fp-c")
    assert len(state.template_visits) == 3


def test_record_visit_updates_current_template():
    state = AutopilotState(goal="x")
    state.record_visit("Home", "https://x.com/", fingerprint="fp-a")
    assert state.current_template == "fp-a"
    state.record_visit("List", "https://x.com/", fingerprint="fp-b")
    assert state.current_template == "fp-b"


def test_record_visit_without_fingerprint_is_noop():
    state = AutopilotState(goal="x")
    state.record_visit("x", "https://x.com/", fingerprint="")
    assert state.template_visits == {}
    assert state.current_template == ""


def test_render_visited_empty():
    state = AutopilotState(goal="x")
    assert "(none yet)" in state.render_visited()


def test_render_visited_shows_template_letters():
    state = AutopilotState(goal="x")
    state.record_visit("Home", "https://x.com/", fingerprint="fp-a")
    state.record_visit("List", "https://x.com/", fingerprint="fp-b")
    rendered = state.render_visited()
    assert "Template A" in rendered
    assert "Template B" in rendered


def test_render_visited_marks_current_page():
    state = AutopilotState(goal="x")
    state.record_visit("Home", "https://x.com/", fingerprint="fp-a")
    state.record_visit("List", "https://x.com/", fingerprint="fp-b")
    rendered = state.render_visited()
    # Last-visited template is marked as current
    assert "CURRENT PAGE" in rendered
    # The List template (fp-b, which is Template B) should be current
    current_line = [l for l in rendered.split("\n") if "CURRENT PAGE" in l]
    assert len(current_line) == 1
    assert "Template B" in current_line[0]


def test_render_visited_flags_overvisited_templates():
    state = AutopilotState(goal="x")
    state.record_visit("Home", "https://x.com/", fingerprint="fp-a")
    state.record_visit("Home", "https://x.com/", fingerprint="fp-a")
    state.record_visit("Home", "https://x.com/", fingerprint="fp-a")
    state.record_visit("List", "https://x.com/", fingerprint="fp-b")
    rendered = state.render_visited()
    # fp-a has 3 visits and is not current → AVOID warning
    assert "AVOID" in rendered


def test_render_visited_shows_singular_plural():
    state = AutopilotState(goal="x")
    state.record_visit("Home", "https://x.com/", fingerprint="fp-a")
    assert "1 time " in state.render_visited() or "1 time\n" in state.render_visited() or "1 time" in state.render_visited()
    state.record_visit("List", "https://x.com/", fingerprint="fp-b")
    state.record_visit("List", "https://x.com/", fingerprint="fp-b")
    assert "2 times" in state.render_visited()


def test_letter_assignment_stable():
    state = AutopilotState(goal="x")
    assert state._letter_for_template("fp-a") == "A"
    assert state._letter_for_template("fp-b") == "B"
    assert state._letter_for_template("fp-a") == "A"  # stable on repeat
    assert state._letter_for_template("fp-c") == "C"


# ── Stuck detection ──


def test_is_stuck_on_current_template_below_threshold():
    state = AutopilotState(goal="x")
    state.record_visit("Home", "https://x.com/", fingerprint="fp-a")
    state.record_visit("Home", "https://x.com/", fingerprint="fp-a")
    state.record_visit("Home", "https://x.com/", fingerprint="fp-a")
    assert not state.is_stuck_on_current_template(threshold=4)


def test_is_stuck_on_current_template_at_threshold():
    state = AutopilotState(goal="x")
    for _ in range(4):
        state.record_visit("Home", "https://x.com/", fingerprint="fp-a")
    assert state.is_stuck_on_current_template(threshold=4)


def test_is_stuck_without_current_template():
    state = AutopilotState(goal="x")
    assert not state.is_stuck_on_current_template()


# ── Prompt construction ──


def test_build_user_prompt_includes_goal_and_step():
    state = AutopilotState(goal="review signup", max_steps=10, step=2)
    state.history.append(AutopilotAction("CLICK", target="Sign up"))
    prompt = build_user_prompt(state, "https://x.com/signup")
    assert "review signup" in prompt
    assert "https://x.com/signup" in prompt
    assert "STEP: 3 of 10" in prompt
    assert 'CLICK "Sign up"' in prompt


def test_build_user_prompt_no_history():
    state = AutopilotState(goal="x", max_steps=5)
    prompt = build_user_prompt(state, "https://x.com")
    assert "(none)" in prompt


# ── System prompt + vocabulary ──


def test_valid_verbs_complete():
    assert VALID_VERBS == {"CLICK", "FILL", "NAVIGATE", "SCROLL", "DONE", "STOP"}


def test_system_prompt_lists_all_verbs():
    for verb in VALID_VERBS:
        assert verb in SYSTEM_PROMPT


def test_system_prompt_forbids_repetition():
    assert "Never repeat" in SYSTEM_PROMPT


def test_user_prompt_template_has_placeholders():
    for placeholder in ("{goal}", "{current_url}", "{step}", "{max_steps}", "{history}"):
        assert placeholder in USER_PROMPT_TEMPLATE


# ── Action log rendering ──


def test_render_action_log_has_goal_and_steps():
    entries = [
        ActionLogEntry(
            step=1, url_before="https://x.com",
            action=AutopilotAction("CLICK", target="Sign up"),
            success=True, message="clicked text",
        ),
        ActionLogEntry(
            step=2, url_before="https://x.com/signup",
            action=AutopilotAction("FILL", target="input.email", value="a@b.com"),
            success=True, message="filled",
        ),
    ]
    md = render_action_log(entries, goal="review signup")
    assert "review signup" in md
    assert "Steps taken:** 2" in md
    assert "Sign up" in md
    assert "input.email" in md


def test_render_action_log_shows_failures():
    entries = [
        ActionLogEntry(
            step=1, url_before="https://x.com",
            action=AutopilotAction("CLICK", target="Ghost"),
            success=False, message="element not found",
        ),
    ]
    md = render_action_log(entries, goal="test")
    assert "FAIL" in md
    assert "element not found" in md


def test_render_action_log_empty():
    md = render_action_log([], goal="nothing happened")
    assert "nothing happened" in md
    assert "Steps taken:** 0" in md
