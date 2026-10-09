import re

from zerver.lib.email_notifications import convert_html_to_markdown


def convert_html_body_to_markdown(html: str) -> str:
    """
    Convert HTML to markdown while preserving task lists.
    Extracts task lists first, converts the rest to markdown, then merges them back.
    """
    # Pattern to match entire task lists
    # Matches: <ul data-type="taskList">...</ul>
    task_list_pattern = r'<ul[^>]*data-type="taskList"[^>]*>.*?</ul>'

    # Extract all task lists and replace with placeholders
    task_lists: list[str] = []
    placeholder_template = "TASK_LIST_PLACEHOLDER_{}"

    def extract_task_list(match: re.Match[str]) -> str:
        task_list_html = match.group(0)
        placeholder = placeholder_template.format(len(task_lists))
        task_lists.append(task_list_html)
        return placeholder

    html_with_placeholders = re.sub(task_list_pattern, extract_task_list, html, flags=re.DOTALL)

    # Convert the rest to markdown
    markdown = convert_html_to_markdown(html_with_placeholders)

    # Convert each extracted task list to markdown
    def convert_task_list_to_markdown(task_list_html: str) -> str:
        """Convert a single task list to markdown code block format."""
        # Pattern to match task list items
        item_pattern = r'<li[^>]*data-checked="(true|false)"[^>]*>.*?<div>(.*?)</div>\s*</li>'

        items = []
        for match in re.finditer(item_pattern, task_list_html, flags=re.DOTALL):
            checked = match.group(1)
            content_html = match.group(2)
            # Extract text content from the HTML (removing <p> tags etc)
            content = re.sub(r"<[^>]+>", "", content_html).strip()
            checkbox = "[x]" if checked == "true" else "[ ]"
            items.append(f"{checkbox} {content}")

        if items:
            task_list_content = "\n".join(items)
            return f"```\n{task_list_content}\n```"
        return ""

    # Replace placeholders with converted task lists
    for i, task_list_html in enumerate(task_lists):
        placeholder = placeholder_template.format(i)
        task_list_md = convert_task_list_to_markdown(task_list_html)
        markdown = markdown.replace(placeholder, task_list_md)

    return markdown
