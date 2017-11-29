# The Zulip Roadmap

Zulip has received a great deal of interest and attention since it was
released as free and open source software by Dropbox.  That attention
has come with a lot of active development work from members of the
Zulip community.

From when Zulip was released as open source in late September 2015
through today (early November, 2017), more than 350 people have
contributed over 5000 pull requests to the various Zulip repositories,
the vast majority of which were submitted by Zulip's users around the
world (as opposed to the small core team that reviews and merges the
pull requests).  In the early days, the Zulip community prepared a
roadmap every 6 month or so with a list of everything major we wanted
to fix in the project.  After 6 months, when we started working on the
next roadmap, we'd find that most of the projects not already done
probably didn't belong on the roadmap at all, and most of what was
being worked on was projects that we realized were important after
adding that roadmap.

In order to address those workflow problems, we've moved to a model
where we maintain the project's priorities continuously through a set
of labels on GitHub that we add to feature ideas when feedback
indicates it is one of the more important improvements Zulip needs:

* [blocker priority][label-blocker] issues are "release-critical".
  Our goal is to resolve all issues on this list before each major
  Zulip release.
* [high priority][label-high] issues are important improvements that
  the project's leadership believes would significantly improve the
  project.

While the Zulip core team focuses our effort on these priority issues,
we also encourage newer contributors to work on resolving priority
issues.

That said, it's important to emphasize that issues without a priority
label are often still valuable to fix, and the majority of issues
fixed in regular Zulip development resolve an issue that was not
tagged as a priority.

This is as it should be: while it's essential to make progress on
these priority projects, the Zulip community feels strongly that all
the little issues are, in aggregate, just as important as the priority
projects.

We welcome participation from the community in influencing the Zulip
roadmap.  If a bug or missing feature is causing significant pain for
your organization, we appreciate your commenting to that effect,
either in [chat.zulip.org](chat-zulip-org.html) or on the relevant
GitHub issue, with an explanation of how the issue impacts your use
case.

[label-blocker]:
https://github.com/zulip/zulip/issues?q=is%3Aissue+is%3Aopen+label%3A%22priority%3A+blocker%22
[label-high]:
https://github.com/zulip/zulip/issues?q=is%3Aissue+is%3Aopen+label%3A%22priority%3A+high%22
