# Zulip GitHub Actions integration

Get Zulip notifications from GitHub Actions workflow runs!

{start_tabs}

1.  {!create-a-generic-bot.md!}

1.  Add the `zulip/github-actions-zulip/send-message@v1` action to your
    GitHub Actions [workflow file][workflows].

    Use the details of the generic bot created above for the `ZULIP_API_KEY`
    secret and the `email` template parameter. The `content` template
    parameter supports Markdown and [GitHub Actions expressions][expressions].

{end_tabs}

!!! tip ""

    A separate `run` GitHub Actions step can help conditionally
    construct the notification content.

### Example templates

{start_tabs}

{tab|send-channel-message}

1.  The following template will send a message to a Zulip channel.

    This example sends a message to the "Scheduled backups" topic in a Zulip
    channel named **github-actions updates** if a previous GitHub Actions
    step with the ID "backup" fails.

      ```
      {% raw %}- name: Send a channel message
      if: steps.backup.outcome == 'failure'
      uses: zulip/github-actions-zulip/send-message@v1
      with:
         api-key: ${{ secrets.ZULIP_API_KEY }}
         email: "github-actions-generic-bot@example.com"
         organization-url: "https://your-org.zulipchat.com"
         to: "github-actions updates"
         type: "stream"
         topic: "scheduled backups"
         content: "Backup [failed](https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }}) at <time:${{ steps.backup.outputs.time }}>.\n>${{ steps.backup.outputs.error }}"{% endraw %}
      ```

{tab|send-dm}

1.  Look up the ID of the recipient for DM notifications in their
    [profile](/help/view-someones-profile).

1.  The following template will send a direct message to a Zulip user.

    This example sends a direct message to the Zulip user with the user ID
    `295`. The `content` parameter here uses the output from a previous
    GitHub Actions step with the ID "construct_message".

      ```
      {%raw%}- name: Send a direct message
      uses: zulip/github-actions-zulip/send-message@v1
      with:
         api-key: ${{ secrets.ZULIP_API_KEY }}
         email: "github-actions-generic-bot@example.com"
         organization-url: "https://your-org.zulipchat.com"
         to: "295"
         type: "private"
         content: "${{ steps.construct_message.outputs.content }}"{% endraw %}
      ```

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/github-actions/001.png)

### Related documentation

* [Configuring the Send Message Action][README]

* [Zulip GitHub Actions repository][repo]

* [GitHub integration](/integrations/doc/github)

[README]: https://github.com/zulip/github-actions-zulip/blob/main/send-message/README.md
[repo]: https://github.com/zulip/github-actions-zulip
[expressions]: https://docs.github.com/en/actions/reference/evaluate-expressions-in-workflows-and-actions
[workflows]: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
