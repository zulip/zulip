from datetime import datetime, timezone
from typing import TypedDict

# For integrations that don't have example webhook fixtures/payloads,
# we create an Zulip notification message content and topic here in
# order to generate an example screenshot to include in the documentation
# page for those integrations.

# To keep these screenshots consistent and easy to review, there are
# shared string constants to use for common content in these integration
# notification messages/templates.

THREE_DIGIT_NUMBER = "492"

# Example user content
BO_NAME = "Bo Williams"
BO_GIT_NAME = "bo-williams"

KEVIN_NAME = "Kevin Lin"

# Example project content
PROJECT_NAME = "Example Project"
PROJECT_PATH_PERFORCE = "//depot/zerver/example-project/*"
PROJECT_STAGE = "production"

VERSION_NUMBER = "v9.2.3"
REVISION_NUMBER = THREE_DIGIT_NUMBER

# Example branch content
BRANCH_GIT = "main"
BRANCH_MERCURIAL = "default"
BRANCH_SVN = "trunk"

# Example commit content
COMMIT_MESSAGE_A = "Optimize image loading in catalog."
COMMIT_MESSAGE_B = 'Suppress "comment edited" events when body is unchanged.'
COMMIT_BODY_A = "Implement lazy loading for images in the catalog to improve load times."

COMMIT_HASH_A = "a2e84e86ddf7e7f8a9b0c1d2e3f4a5b6c7d8e9f0"
COMMIT_HASH_B = "9fceb02c0c4b8e4c1e7b43hd4e5f6a7b8c9d0e1f"
DEPLOYMENT_HASH = "e494a5be3393"

# Example task/issue/ticket content
TASK_TITLE = COMMIT_MESSAGE_A[:-1]
TASK_DESCRIPTION = COMMIT_BODY_A
TICKET_NUMBER = THREE_DIGIT_NUMBER

# Example datetime content
_DT = datetime(2025, 5, 30, 2, 0, 0, tzinfo=timezone.utc)

DATETIME_STAMP = _DT.strftime("%Y-%m-%d %H:%M:%S")
DATETIME_GLOBAL = f"<time:{_DT.strftime('%Y-%m-%dT%H:%M:%S%z')}>"

DATE_ISO_8601 = _DT.strftime("%Y-%m-%d")
DATE_LONG = _DT.strftime("%A, %B %d, %Y")


class ScreenshotContent(TypedDict):
    topic: str
    content: str


ASANA = ScreenshotContent(
    topic=PROJECT_NAME,
    content=f"{BO_NAME} created a new task **[{TASK_TITLE}]()**.\n> {TASK_DESCRIPTION}",
)

CAPISTRANO = ScreenshotContent(
    topic=PROJECT_NAME,
    content=f"The [deployment]() to **{PROJECT_STAGE}** (version {VERSION_NUMBER}) has been completed successfully! :rocket:",
)

CODEBASE = ScreenshotContent(
    topic=f"Push to {BRANCH_GIT} on {PROJECT_NAME}",
    content=f"""{BO_NAME} pushed 2 commit(s) to `{BRANCH_GIT}` in project {PROJECT_NAME}:

* [{COMMIT_HASH_A[:10]}](): {COMMIT_MESSAGE_A}
* [{COMMIT_HASH_B[:10]}](): {COMMIT_MESSAGE_B}
""",
)

DISCOURSE = ScreenshotContent(
    topic="chat",
    content=f"""**@{BO_NAME}** posted in [Example channel]()
> {COMMIT_BODY_A}""",
)

GITHUB_ACTIONS = ScreenshotContent(
    topic="scheduled backups",
    content=f"""Backup [failed]() at {DATETIME_STAMP}.
> Unable to connect.""",
)

GOOGLE_CALENDAR = ScreenshotContent(
    topic="Team reminders",
    content=f"""The [Development Sync]() event is scheduled from 2 PM - 3 PM on {DATE_LONG} at Conference Room B.
> Let's align on our current sprint progress, address any blockers, and share updates. Your input is crucial!

[Join call]().""",
)

JENKINS = ScreenshotContent(
    topic=PROJECT_NAME,
    content=f"**Build:** [#{REVISION_NUMBER}](): FAILURE :cross_mark:",
)

MASTODON = ScreenshotContent(
    topic="MIT Technology Review",
    content=f"""**[Don’t let hype about AI agents get ahead of reality](https://www.technologyreview.com/2025/07/03/1119545/dont-let-hype-about-ai-agents-get-ahead-of-reality/)**
Google’s recent unveiling of what it calls a “new class of agentic experiences” feels like a turning point. At its I/O event last month, for example, the company showed off a digital assistant that didn’t just answer questions; it helped work on a bicycle repair by finding a matching user manual, locating a YouTube…
https://www.technologyreview.com/{DATE_ISO_8601.replace("-", "/")}/1119545/dont-let-hype-about-ai-agents-get-ahead-of-reality/""",
)

MERCURIAL = ScreenshotContent(
    topic=BRANCH_MERCURIAL,
    content=f"""**{BO_NAME}** pushed [2 commits]() to **{BRANCH_MERCURIAL}** (`{REVISION_NUMBER}:{DEPLOYMENT_HASH[:12]}`):
* [{COMMIT_MESSAGE_A}]()
* [{COMMIT_MESSAGE_B}]()
""",
)

NAGIOS = ScreenshotContent(
    topic="service Remote Load on myserver.example.com",
    content="""**PROBLEM**: service is CRITICAL
~~~~
CRITICAL - load average: 7.49, 8.20, 4.72
~~~~
""",
)

NOTION = ScreenshotContent(
    topic=f"{PROJECT_NAME} Release {VERSION_NUMBER}",
    content=f"""**{BO_NAME}** [commented]() on:
> project demo scheduled

Can we reschedule this to next week?""",
)

OPENSHIFT = ScreenshotContent(
    topic=PROJECT_NAME,
    content=f"""Deployment [{REVISION_NUMBER}]() triggered by a push to **{BRANCH_GIT}** by commit [{COMMIT_HASH_A[:7]}]() at {DATETIME_STAMP} has **failed**.""",
)

PERFORCE = ScreenshotContent(
    topic=PROJECT_PATH_PERFORCE,
    content=f"""
**{BO_NAME}** committed revision @[{REVISION_NUMBER}]() to `{PROJECT_PATH_PERFORCE}`.

```quote
{COMMIT_MESSAGE_A}
```
""",
)

PUPPET = ScreenshotContent(
    topic="Reports",
    content=f"""Puppet production run for web-server-01 completed at {DATETIME_GLOBAL}. [GitHub Gist]() | [Report URL]()""",
)

REDMINE = ScreenshotContent(
    topic=TASK_TITLE,
    content=f"""{BO_NAME} **created** issue [{TICKET_NUMBER} {TASK_TITLE}]():

~~~quote

{TASK_DESCRIPTION}...

~~~

* **Assignee**: {KEVIN_NAME}
* **Status**: New
* **Target version**: {VERSION_NUMBER[1:]}
* **Estimated hours**: 40""",
)

RSS = MASTODON

SVN = ScreenshotContent(
    topic=PROJECT_NAME,
    content=f"""**{BO_GIT_NAME}** committed revision r{REVISION_NUMBER} to `{BRANCH_SVN}`.
> {COMMIT_MESSAGE_A}
""",
)

TRAC = ScreenshotContent(
    topic=f"#{TICKET_NUMBER} {TASK_TITLE}",
    content=f"""**{BO_GIT_NAME}** updated [ticket #{TICKET_NUMBER}]() with comment:
> Fixed in  {COMMIT_HASH_A}

status: **new** => **closed**, resolution: => **fixed**""",
)
