# Zulip Open Source Contributor Quickstart Guide

Zulip is an open-source real-time team collaboration platform with powerful topic-based threading.
This guide outlines the documentation authoring workflow for new community contributors.

## Prerequisites

Before submitting documentation changes, ensure you have:
- A GitHub account with a fork of `zulip/zulip`
- Git configured with your developer name and email
- Python 3.x installed for local validation

## Contribution Workflow

Follow standard Git branching practices:

```bash
# Clone personal fork
git clone https://github.com/tukaram-007/zulip.git
cd zulip

# Create dedicated topic branch
git checkout -b feat/markdown-docs-quality-validator
```

## Documentation Guidelines

1. Always use clear, accessible language.
2. Ensure all external and internal links are valid.
3. Enclose CLI commands and code snippets in triple backticks.
