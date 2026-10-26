# How to Contribute to Zulip Documentation

This guide provides simple, step-by-step instructions for contributors to submit clear and compliant Markdown documentation updates to Zulip.

## Overview

Zulip welcomes contributions from open-source developers worldwide. Contributing documentation requires following standard Markdown formatting and disciplined Git workflows.

## Contribution Steps

1. **Fork the Upstream Repository**:
   Fork `zulip/zulip` to your personal GitHub account (`tukaram-007`).

2. **Clone and Branch**:
   Clone your fork locally and create a descriptive feature branch:
   ```bash
   git clone https://github.com/tukaram-007/zulip.git
   git checkout -b feat/markdown-docs-quality-validator
   ```

3. **Author or Edit Markdown**:
   - Write clear, concise explanations.
   - Use standard code blocks with language identifiers (e.g., `bash`, `python`).
   - Ensure all relative and external links point to active resources.

4. **Verify Locally with Validator Tool**:
   Run the lightweight documentation quality validator before pushing:
   ```bash
   python zulip_doc_validator.py docs/how-to/quick-contributor-guide.md
   ```

5. **Commit and Push**:
   ```bash
   git add docs/how-to/quick-contributor-guide.md
   git commit -m "docs: add quick contributor guide for documentation authors"
   git push -u origin feat/markdown-docs-quality-validator
   ```
