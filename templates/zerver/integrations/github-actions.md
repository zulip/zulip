# Zulip GitHub Actions integration

Get Zulip notifications from GitHub Actions!

{start_tabs}

1.  {!create-a-generic-bot.md!}

1.  To send Zulip notifications from your workflow runs, add the
    `zulip/github-actions-zulip/send-message@v1` action to your GitHub
    Actions workflow file, and set the input values as demonstrated in the
    example templates below.

    Use the details of the generic bot created above for the `ZULIP_API_KEY`
    secret and the `email` template parameter.

    The `content` template parameter supports Markdown and
    [GitHub Actions expressions][expressions].

1.  The following template will send a message to a Zulip channel. This
    example posts to the "Scheduled backups" topic in a Zulip channel named
    **#github-actions updates**, if a previous GitHub Actions step with the
    id "backup" fails.

      ```
      {% raw %}- name: Send a channel message
      if: steps.backup.outcome == 'failure'
      uses: zulip/github-actions-zulip/send-message@v1
      with:
         api-key: ${{ secrets.ZULIP_API_KEY }}
         email: "github-actions-generic-bot@example.com"
         organization-url: "https://your-zulip-org.com"
         to: "github-actions updates"
         type: "stream"
         topic: "scheduled backups"
         content: "Backup failed at ${{ github.event.schedule }}.\n>${{ steps.backup.outputs.error }}"{% endraw %}
      ```

1.  The following template will send a direct message to a Zulip user. This
    example posts to the Zulip user with the user ID `295`. The `content`
    parameter here uses the output from a previous step "construct_message";
    a separate `run` step can help conditionally construct the message
    content.

      ```
      {%raw%}- name: Send a direct message
      uses: zulip/github-actions-zulip/send-message@v1
      with:
         api-key: ${{ secrets.ZULIP_API_KEY }}
         email: "github-actions-generic-bot@example.com"
         organization-url: "https://your-zulip-org.com"
         to: "295"
         type: "private"
         content: "${{ steps.construct_message.outputs.content }}"{% endraw %}
      ```

{end_tabs}

### Related documentation

* [Configuring the Send Message Action][README]

* [Zulip GitHub Actions repository][repo]

* [GitHub integration](/integrations/doc/github)

[README]: https://github.com/zulip/github-actions-zulip/blob/main/send-message/README.md
[repo]: https://github.com/zulip/github-actions-zulip
[expressions]: https://docs.github.com/en/actions/reference/evaluate-expressions-in-workflows-and-actions
