# Reporting bugs

There are several ways to report bugs (or possible bugs) you encounter in Zulip:

- If you have a concrete bug report with steps to reproduce the behavior, [file an
  issue](#filing-a-github-issue) in the appropriate GitHub repository.
- If you are not sure whether the issue you encountered is a bug, or how to
  reproduce it, [start a
  conversation](#starting-a-conversation-about-a-possible-bug) in the Zulip
  development community.
- To report a possible security issue, contact Zulip's security team at
  [security@zulip.com](mailto:security@zulip.com). _Do not_ report security issues
  publicly (in GitHub or in the Zulip development community). We create a CVE for
  every security issue in our released software.
- If reporting a bug requires sharing private details about your
  organization, email [support@zulip.com](mailto:support@zulip.com).

No matter where you report the bug, please follow the instructions below for
what to include in a bug report.

## What to include in a bug report

1. **Describe** what you were expecting to see, what you saw instead, and steps
   that may help others reproduce the surprising behavior you experienced.
   Include screenshots and/or screen captures (see [recommended
   tools](../tutorials/screenshot-and-gif-software.md)) if they help
   communicate what you are describing, but avoid posting long videos.
1. **Indicate the [version](https://zulip.com/help/view-zulip-version)** of the
   Zulip app where you encountered the bug. It may also be helpful to note your
   operating system, whether you are using the web app or the desktop app, and
   your browser if using the web app.

## Filing a GitHub issue

Filing a GitHub issue works best when:

- You are confident that the behavior you encountered is a bug, not some quirk
  of how a feature works that may turn out to be intentional.
- You can describe clearly what you were expecting to see, and what you saw instead.
- You can provide steps for someone else to reproduce the issue you encountered.
  This is important for developers to be able to fix the bug, and test that
  their fix worked.

If all of the above accurately describe your situation, please file an issue!
Otherwise, we recommend [starting a
conversation](#starting-a-conversation-about-a-possible-bug) in the Zulip
development community so that the problem you encountered can be discussed
interactively.

Steps and best practices for filing a GitHub issue:

1. Report the issue in the **appropriate [Zulip
   repository](https://github.com/zulip)**. The most commonly used repositories
   are:
   - [zulip/zulip](https://github.com/zulip/zulip/issues) for issues with the
     Zulip web app or server. A good default if you aren't sure which repository
     to use.
   - [zulip/zulip-mobile](https://github.com/zulip/zulip-mobile/issues) for
     issues with the mobile apps.
   - [zulip/zulip-desktop](https://github.com/zulip/zulip-desktop/issues) for
     issues that are specific to the Zulip desktop app, and therefore _do not_
     occur in the web app.
   - [zulip/zulip-terminal](https://github.com/zulip/zulip-terminal/issues) for
     issues with the terminal app.
2. Do a **quick search** of the repository to see if your issue has already
   been filed. If it has, you can add a comment if that seems helpful.
3. If you are aware of a related discussion in the Zulip development community,
   please **cross-link** between the issue and the discussion thread. [Link to a
   specific
   message](https://zulip.com/help/link-to-a-message-or-conversation#get-a-link-to-a-specific-message)
   in the discussion thread, as message links will still work even if the topic is
   renamed or resolved.

To encourage prompt attention and discussion for a bug report you have filed,
you can send a message in the Zulip development community with the key points
from your report. Be sure to [link to the GitHub
issue](https://zulip.com/development-community/#linking-to-github-issues-and-pull-requests).
See the following section for advice on where and how to start the conversation.

## Starting a conversation about a possible bug

If you are not sure whether the issue you encountered is a bug, or how to
reproduce it, we highly recommend reporting it in the [Zulip development
community](https://zulip.com/development-community/). It's the best place to
interactively discuss your problem.

Steps and best practices for starting a conversation:

1. [**Join** the Zulip development
   community](https://zulip.com/development-community/) if you don't already
   have an account.
2. Pick an **appropriate stream** to report your issue:
   - [#issues](https://chat.zulip.org/#narrow/stream/9-issues) for issues with
     the Zulip web app or server. Use this stream if you aren't sure which
     stream is most appropriate.
   - [#mobile](https://chat.zulip.org/#narrow/stream/48-mobile) for issues with
     the mobile apps.
   - [#desktop](https://chat.zulip.org/#narrow/stream/16-desktop) for issues
     that are specific to the Zulip desktop app, and therefore _do not_
     occur in the web app.
   - [#zulip-terminal](https://chat.zulip.org/#narrow/stream/206-zulip-terminal)
     for issues with the terminal app.
   - [#production
     help](https://chat.zulip.org/#narrow/stream/31-production-help) for issues
     related to self-hosting Zulip. See the [troubleshooting
     guide](../production/troubleshooting.md) for additional details.
3. **[Start a new topic](https://zulip.com/help/starting-a-new-topic)** for
   discussing your issue, using a brief summary of the issue as the name of the topic.

If you aren't sure where to post or how to name your topic, don't worry!
Moderators can always rename the topic, or move the thread to another stream.

Once a possible bug is reported, members of the development community will jump
in to discuss whether the report constitutes a bug, how to reproduce it, and how
it can be resolved. The initial reporter can help by monitoring the discussion
and replying to any follow-up questions. If the report is determined to be a
reproducible bug, a GitHub issue will be filed to keep track of it (see below).

## Managing bug reports

This section describes our process for managing bugs. All community members are
encouraged to help make sure this process runs smoothly, whether or not they
originally reported the bug.

Whenever a bug is tracked in GitHub and also discussed in the development
community, be sure to cross-link between the issue and the conversation. [Link
to a specific
message](https://zulip.com/help/link-to-a-message-or-conversation#get-a-link-to-a-specific-message)
in the discussion thread, as message links will still work even if the topic is
renamed or resolved.

- If you encounter a definite bug with a clear reproducer and significant user
  impact, it is best to both file a GitHub issue and immediately start a
  discussion in the development community. This helps us address important
  issues as quickly as possible.
- For minor bugs (e.g., a visual glitch in a settings menu for very long stream
  names), filing a GitHub issue is sufficient.
- If a potential bug discussed in the development community is confirmed to be
  an actual, reproducible bug, anyone can help out by filing a GitHub issue to
  track it:
  - In some cases, especially if we're planning to fix the issue right away, the
    GitHub issue description can simply quote and link to a message from the
    discussion in the development community -- no need to stress over making it
    perfect.
  - [Use Zulipbot](../contributing/zulipbot-usage.md) to add the appropriate
    labels, including “bug” and at least one area label; leave a comment on
    the issue if you don't know what area labels to use.
  - You can add the “help wanted” label (and claim the issue if you like) if
    that is appropriate based on the discussion. Note that sometimes we won't
    mark a reproducible bug as “help wanted” for various reasons. For example,
    we might want a core contributor to take it on, or the fix might be planned
    as part of a larger project.
  - Don't forget to cross-link between the issue and the discussion.
- If a bug report in GitHub is not sufficiently clear, Zulip maintainers will
  often encourage the reporter to discuss it interactively in the development
  community.
