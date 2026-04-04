---
id: int-001
title: "Form Design Best Practices"
category: interaction
tags: [forms, usability, input, validation, interaction]
source: "https://www.lukew.com/resources/web_form_design.asp"
source_authority: canonical
ingested: 2026-04-04
validated: true
validator_notes: "Based on Wroblewski (2008) research from Yahoo! and eBay"
---

## Label Placement

| Position | Completion Time | Best For |
|----------|----------------|----------|
| Top-aligned | Fastest | Most forms - labels above inputs |
| Right-aligned | Moderate | Data-dense forms with space constraints |
| Left-aligned | Slowest | Unfamiliar or complex data |
| Inline/Placeholder | Problematic | Never as sole label - disappears on focus |

## Key Principles

1. **One column layout** - Multi-column form layouts slow completion and increase errors. Exception: short, related fields (city/state/zip).

2. **Group related fields** - Use fieldsets and visual grouping. 5-7 fields per group maximum.

3. **Show requirements before input** - Format hints, character limits, and field descriptions should appear before or during input, not only after errors.

4. **Inline validation on blur** - Validate as users leave each field, not on submit. Show success states too, not just errors.

5. **Descriptive button labels** - "Create Account" not "Submit". "Save Changes" not "OK". The button label should describe the action outcome.

6. **Never clear form data on error** - Preserve all user input when showing validation errors.

7. **Mark optional fields, not required** - If most fields are required, mark the few that are optional. Use "(optional)" text, not asterisks.

## Common Violations
- Placeholder text as the only label (disappears on focus)
- Generic "Submit" button labels
- Validation only on form submission, not inline
- Clearing form data when errors occur
- Required fields marked with only a colour change
