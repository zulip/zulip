#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Zulip hook for Mercurial changeset pushes.
# Copyright Â© 2012-2014 Zulip, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
#
# This hook is called when changesets are pushed to the master repository (ie
# `hg push`). See https://zulipchat.com/integrations for installation instructions.
from __future__ import absolute_import

import zulip
from six.moves import range

VERSION = "0.9"

def format_summary_line(web_url, user, base, tip, branch, node):
    """
    Format the first line of the message, which contains summary
    information about the changeset and links to the changelog if a
    web URL has been configured:

    Jane Doe <jane@example.com> pushed 1 commit to master (170:e494a5be3393):
    """
    revcount = tip - base
    plural = "s" if revcount > 1 else ""

    if web_url:
        shortlog_base_url = web_url.rstrip("/") + "/shortlog/"
        summary_url = "{shortlog}{tip}?revcount={revcount}".format(
            shortlog=shortlog_base_url, tip=tip - 1, revcount=revcount)
        formatted_commit_count = "[{revcount} commit{s}]({url})".format(
            revcount=revcount, s=plural, url=summary_url)
    else:
        formatted_commit_count = "{revcount} commit{s}".format(
            revcount=revcount, s=plural)

    return u"**{user}** pushed {commits} to **{branch}** (`{tip}:{node}`):\n\n".format(
        user=user, commits=formatted_commit_count, branch=branch, tip=tip,
        node=node[:12])

def format_commit_lines(web_url, repo, base, tip):
    """
    Format the per-commit information for the message, including the one-line
    commit summary and a link to the diff if a web URL has been configured:
    """
    if web_url:
        rev_base_url = web_url.rstrip("/") + "/rev/"

    commit_summaries = []
    for rev in range(base, tip):
        rev_node = repo.changelog.node(rev)
        rev_ctx = repo.changectx(rev_node)
        one_liner = rev_ctx.description().split("\n")[0]

        if web_url:
            summary_url = rev_base_url + str(rev_ctx)
            summary = "* [{summary}]({url})".format(
                summary=one_liner, url=summary_url)
        else:
            summary = "* {summary}".format(summary=one_liner)

        commit_summaries.append(summary)

    return "\n".join(summary for summary in commit_summaries)

def send_zulip(email, api_key, site, stream, subject, content):
    """
    Send a message to Zulip using the provided credentials, which should be for
    a bot in most cases.
    """
    client = zulip.Client(email=email, api_key=api_key,
                          site=site,
                          client="ZulipMercurial/" + VERSION)

    message_data = {
        "type": "stream",
        "to": stream,
        "subject": subject,
        "content": content,
    }

    client.send_message(message_data)

def get_config(ui, item):
    try:
        # configlist returns everything in lists.
        return ui.configlist('zulip', item)[0]
    except IndexError:
        return None

def hook(ui, repo, **kwargs):
    """
    Invoked by configuring a [hook] entry in .hg/hgrc.
    """
    hooktype = kwargs["hooktype"]
    node = kwargs["node"]

    ui.debug("Zulip: received {hooktype} event\n".format(hooktype=hooktype))

    if hooktype != "changegroup":
        ui.warn("Zulip: {hooktype} not supported\n".format(hooktype=hooktype))
        exit(1)

    ctx = repo.changectx(node)
    branch = ctx.branch()

    # If `branches` isn't specified, notify on all branches.
    branch_whitelist = get_config(ui, "branches")
    branch_blacklist = get_config(ui, "ignore_branches")

    if branch_whitelist:
        # Only send notifications on branches we are watching.
        watched_branches = [b.lower().strip() for b in branch_whitelist.split(",")]
        if branch.lower() not in watched_branches:
            ui.debug("Zulip: ignoring event for {branch}\n".format(branch=branch))
            exit(0)

    if branch_blacklist:
        # Don't send notifications for branches we've ignored.
        ignored_branches = [b.lower().strip() for b in branch_blacklist.split(",")]
        if branch.lower() in ignored_branches:
            ui.debug("Zulip: ignoring event for {branch}\n".format(branch=branch))
            exit(0)

    # The first and final commits in the changeset.
    base = repo[node].rev()
    tip = len(repo)

    email = get_config(ui, "email")
    api_key = get_config(ui, "api_key")
    site = get_config(ui, "site")

    if not (email and api_key):
        ui.warn("Zulip: missing email or api_key configurations\n")
        ui.warn("in the [zulip] section of your .hg/hgrc.\n")
        exit(1)

    stream = get_config(ui, "stream")
    # Give a default stream if one isn't provided.
    if not stream:
        stream = "commits"

    web_url = get_config(ui, "web_url")
    user = ctx.user()
    content = format_summary_line(web_url, user, base, tip, branch, node)
    content += format_commit_lines(web_url, repo, base, tip)

    subject = branch

    ui.debug("Sending to Zulip:\n")
    ui.debug(content + "\n")

    send_zulip(email, api_key, site, stream, subject, content)
