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
BO_EMAIL = "Bo-Williams@example.com"
BO_GIT_NAME = "bo-williams"

KEVIN_NAME = "Kevin Lin"
KEVIN_EMAIL = "Kevin-Lin@example.com"

# Example project content
PROJECT_NAME = "FizzBuzz"
PROJECT_PATH = "//depot/fizz/buzz/*"
PROJECT_STAGE = "production"

VERSION_NUMBER = "v9.2.3"
REVISION_NUMBER = THREE_DIGIT_NUMBER

# Example branch content
BRANCH = "main"
BRANCH_MERCURIAL = "default"
BRANCH_SVN = "trunk"

# Example commit content
COMMIT_MESSAGE_A = "Optimize image loading in paints catalog."
COMMIT_MESSAGE_B = 'Suppress "comment edited" events when body is same.'
COMMIT_BODY_A = "Implement lazy loading for images on the paints catalog to improve load times."

COMMIT_HASH_A = "a2e84e86ddf7e7f8a9b0c1d2e3f4a5b6c7d8e9f0"
COMMIT_HASH_B = "9fceb02c0c4b8e4c1e7b43hd4e5f6a7b8c9d0e1f2"
DEPLOYMENT_HASH = "e494a5be3393"

# Example task/issue/ticket content
TASK_TITLE = COMMIT_MESSAGE_A[:-1]
TASK_DESCRIPTION = COMMIT_BODY_A
TICKET_NUMBER = THREE_DIGIT_NUMBER

# Example datetime content
_DT = datetime(2025, 5, 30, 2, 0, 0, tzinfo=timezone.utc)

DATETIME_STAMP = _DT.strftime("%Y-%m-%d %H:%M:%S")
DATETIME_ASCTIME = _DT.strftime("%a %b %d %H:%M:%S %Y")
DATETIME_FUSED = _DT.strftime("%Y%m%d%H%M%S")

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
    topic=f"Push to {BRANCH} on {PROJECT_NAME}",
    content=f"""{BO_NAME} pushed 2 commit(s) to `{BRANCH}` in project {PROJECT_NAME}:

* [{COMMIT_HASH_A[:10]}](): {COMMIT_MESSAGE_A}
* [{COMMIT_HASH_B[:10]}](): {COMMIT_MESSAGE_B}
""",
)

DISCOURSE = ScreenshotContent(
    topic="announce",
    content=f"""**@{BO_NAME}** posted in [Zulip's new mobile app is out!]()
> Zulip’s next-gen mobile app is now in public beta. If offers a sleek new design and a faster, smoother experience. Check out the announcement post for details and instructions on how to try the beta!""",
)

GIT = ScreenshotContent(
    topic=BRANCH,
    content=f"""`{DEPLOYMENT_HASH[:12]}` was deployed to `{BRANCH}` with:
* {KEVIN_EMAIL} - {COMMIT_HASH_A[:7]}: {COMMIT_MESSAGE_A}
* {BO_EMAIL} - {COMMIT_HASH_B[:7]}: {COMMIT_MESSAGE_B}
""",
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

NOTION = ScreenshotContent(
    topic=f"{PROJECT_NAME} Release {VERSION_NUMBER}",
    content=f"""**{BO_NAME}** [commented]() on:
> project demo scheduled

Can we reschedule this to next week?""",
)

OPENSHIFT = ScreenshotContent(
    topic=PROJECT_NAME,
    content=f"""Deployment [{REVISION_NUMBER}]() triggered by a push to **{BRANCH}** by commit [{COMMIT_HASH_A[:7]}]() at {DATETIME_STAMP} has **failed**.""",
)

PERFORCE = ScreenshotContent(
    topic=PROJECT_PATH,
    content=f"""
**{BO_NAME}** committed revision @[{REVISION_NUMBER}]() to `{PROJECT_PATH}`.

```quote
{COMMIT_MESSAGE_A}
```
""",
)

PUPPET = ScreenshotContent(
    topic="Reports",
    content=f"""Puppet production run for web-server-01 completed at {DATETIME_ASCTIME}.
 Created a Gist showing the output at {DEPLOYMENT_HASH}
 Summary at report.example.com:{DATE_ISO_8601}/production/web-server-01/completed
 Report URL: http://example.com/puppet-reports/production/web-server-01/?status=completed&time={DATETIME_FUSED}""",
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

FIXTURELESS_INTEGRATIONS: list[str] = [
    "asana",
    "capistrano",
    "codebase",
    "discourse",
    "git",
    "github-actions",
    "google-calendar",
    "jenkins",
    "mastodon",
    "mercurial",
    "notion",
    "openshift",
    "perforce",
    "puppet",
    "redmine",
    "rss",
    "svn",
    "trac",
]
FIXTURELESS_SCREENSHOT_CONTENT: dict[str, list[ScreenshotContent]] = {
    key: [globals()[key.upper().replace("-", "_")]] for key in FIXTURELESS_INTEGRATIONS
}
