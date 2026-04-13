# CI/CD Templates

Ready-to-use pipeline templates for integrating design-intel into your CI/CD workflow.

## Available Templates

| File | Platform | Trigger |
|------|----------|---------|
| `github-actions-design-review.yml` | GitHub Actions | Pull requests to main |
| `github-actions-monitoring.yml` | GitHub Actions | Weekly cron schedule |
| `gitlab-ci-design-review.yml` | GitLab CI/CD | Merge requests |
| `bitbucket-pipelines-design-review.yml` | Bitbucket Pipelines | Pull requests |

## Setup

1. Copy the template for your CI platform into your project
2. Set `DESIGN_REVIEW_URL` to your preview/staging URL
3. (Optional) Store LLM API keys as CI secrets if using LLM-powered features

## Modes

All templates default to **pragmatic mode**, which:
- Grandfathers pre-existing violations (won't fail on old issues)
- Only gates on NEW critical/serious issues introduced by the PR/MR
- Allows a small score fluctuation (default: 2 percentage points)

Add `--strict` for zero-tolerance gating on any A/AA violation.

## Customisation

Common flags you can add to the `design-intel ci` command:

| Flag | Default | Purpose |
|------|---------|---------|
| `--strict` | off | Zero-tolerance mode |
| `--min-score 70` | none | Hard score floor |
| `--severity critical` | serious | Minimum severity that gates |
| `--score-tolerance 5.0` | 2.0 | Allowed score fluctuation |
| `--device iphone-12` | desktop | Test at a specific viewport |
