---
id: int-002
title: "Microinteractions Design Framework"
category: interaction
tags: [microinteractions, feedback, animation, interaction]
source: "Dan Saffer (2013) Microinteractions: Designing with Details"
source_authority: canonical
ingested: 2026-04-04
validated: true
validator_notes: "Saffer's four-component framework, O'Reilly"
---

## Four Components of a Microinteraction

1. **Trigger** - What initiates the microinteraction. User-initiated (click, swipe, voice) or system-initiated (notification, error, state change).

2. **Rules** - What happens once triggered. The logic that determines the microinteraction's behaviour. Should be simple and predictable.

3. **Feedback** - How the system communicates what's happening. Visual (animation, colour change), auditory (click, chime), or haptic (vibration).

4. **Loops and Modes** - What happens over time. Does the interaction repeat? Does it change after multiple uses? Does it have different states?

## Essential UI Microinteractions

| Interaction | Expected Feedback | Common Failure |
|-------------|-------------------|----------------|
| Button click | Visual press state + action result | No feedback, delayed response |
| Form submission | Loading state, then success/error | Page refresh with no indication |
| Toggle/switch | Immediate visual state change | Ambiguous on/off states |
| Pull to refresh | Animation + loading indicator | No indication of refresh state |
| Hover on interactive | Cursor change + visual highlight | No hover state, no cursor change |
| Error state | Red highlight + specific message | Generic "An error occurred" |
| Successful action | Confirmation + next step | No confirmation, user unsure if it worked |

## When to apply
- Every interactive element should have visible state changes (default, hover, active, focus, disabled, loading)
- Feedback should match action significance: minor action = subtle feedback, major action = prominent feedback
- System status changes should always be communicated (loading, saving, syncing)
