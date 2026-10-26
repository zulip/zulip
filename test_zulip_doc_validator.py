import unittest
import os
import tempfile
from zulip_doc_validator import inspect_markdown_file


class TestZulipDocValidator(unittest.TestCase):
    def test_valid_markdown_passes(self):
        content = """# Overview
Zulip is an open-source real-time team collaboration platform.

## Key Features
- Unique topic-based threading model
- 100% open-source with 100+ native integrations

```bash
git clone https://github.com/zulip/zulip.git
```
"""
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(content)
            temp_name = f.name
        try:
            res = inspect_markdown_file(temp_name)
            self.assertEqual(res["status"], "VALID")
            self.assertEqual(len(res["errors"]), 0)
        finally:
            os.remove(temp_name)

    def test_unclosed_code_fence(self):
        content = """# Development Setup
Follow the commands below:

```bash
./tools/provision
"""
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(content)
            temp_name = f.name
        try:
            res = inspect_markdown_file(temp_name)
            self.assertEqual(res["status"], "INVALID")
            self.assertTrue(any("Unclosed Markdown code fence" in e for e in res["errors"]))
        finally:
            os.remove(temp_name)

    def test_empty_link_target(self):
        content = """# Community Resources
Join the official [Zulip Development Community]() stream.
"""
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(content)
            temp_name = f.name
        try:
            res = inspect_markdown_file(temp_name)
            self.assertEqual(res["status"], "INVALID")
            self.assertTrue(any("Empty Markdown link target" in e for e in res["errors"]))
        finally:
            os.remove(temp_name)

    def test_empty_heading_error(self):
        content = """# Section One
Text content here.

## 
"""
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(content)
            temp_name = f.name
        try:
            res = inspect_markdown_file(temp_name)
            self.assertEqual(res["status"], "INVALID")
            self.assertTrue(any("Heading without title" in e for e in res["errors"]))
        finally:
            os.remove(temp_name)

    def test_nonexistent_file_handling(self):
        res = inspect_markdown_file("non_existent_file_xyz_123.md")
        self.assertEqual(res["status"], "INVALID")
        self.assertTrue(any("File not found" in e for e in res["errors"]))

    def test_empty_file_handling(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("   \n  \t  \n")
            temp_name = f.name
        try:
            res = inspect_markdown_file(temp_name)
            self.assertEqual(res["status"], "INVALID")
            self.assertTrue(any("File is empty" in e for e in res["errors"]))
        finally:
            os.remove(temp_name)


if __name__ == "__main__":
    unittest.main()
