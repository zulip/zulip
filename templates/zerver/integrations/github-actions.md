# Zulip GitHub Actions integration

Get Zulip notifications from GitHub Actions!

{start_tabs}

1.  {!create-a-generic-bot.md!}

1.  To send Zulip notifications from your workflow runs, add the
    `zulip/github-actions-zulip/send-message@v1` action to your GitHub
    Actions workflow file, and set the input values as demonstrated in the
    sample templates below.

    Use the details of the generic bot created above for the `api-key` and
    `email` parameters.

1.  Use the following template to send a message to a Zulip channel. This
    example posts to the "Scheduled backups" topic in a Zulip channel named
    "github-actions updates".

      ```
      {% raw %}- name: Send a channel message
      uses: zulip/github-actions-zulip/send-message@v1
      with:
         api-key: ${{ secrets.ZULIP_API_KEY }}
         email: "github-actions-generic-bot@example.com"
         organization-url: "https://your-zulip-org.com"
         to: "github-actions updates"
         type: "stream"
         topic: "Scheduled backups"
         content: "Backup failed at ${{ github.event.schedule }}.\n>${{ steps.backup.outputs.error }}"{% endraw %}
      ```

1.  Use the following template to send a direct message. This example posts
    to the Zulip user with the user ID `295`.

      ```
      {%raw%}- name: Send a direct message
      uses: zulip/github-actions-zulip/send-message@v1
      with:
         api-key: ${{ secrets.ZULIP_API_KEY }}
         email: "github-actions-generic-bot@example.com"
         organization-url: "https://your-zulip-org.com"
         to: "295"
         type: "private"
         content: "Backup failed at ${{ github.event.schedule }}.\n>${{ steps.backup.outputs.error }}"{% endraw %}
      ```

{end_tabs}

### Related documentation

* [Configuring the Send Message Action][README]

* [Zulip GitHub Actions repository][repo]

* [GitHub integration](/integrations/doc/github)

[README]: https://github.com/zulip/github-actions-zulip/blob/main/send-message/README.md
[repo]: https://github.com/zulip/github-actions-zulip
