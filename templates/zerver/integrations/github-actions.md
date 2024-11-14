# Zulip GitHub Actions integration

It's easy to send Zulip messages from GitHub Actions!

{start_tabs}

1. {!create-a-generic-bot.md!}

1. To send Zulip notifications whenever your workflow runs, add the
   `zulip/github-actions-zulip/send-message@v1` action to your GitHub
   Actions workflow file, and set the input values as specified in the
   sample templates below.

1. Use the following template to send a message to a Zulip channel.

      ```
      {% raw %}- name: Send a channel message
      uses: zulip/github-actions-zulip/send-message@v1
      with:
         api-key: ${{ secrets.ZULIP_API_KEY }}
         email: "username@example.com" # email address corresponding to the API key
         organization-url: "https://your-org.zulipchat.com"
         to: "social" # Zulip channel name
         type: "stream"
         topic: "Castle" # Zulip topic name
         content: "I come not, friends, to steal away your hearts." # Markdown message{% endraw %}
      ```

1. Use the following template to send a direct message on Zulip.

      ```
      {%raw%}- name: Send a direct message
      uses: zulip/github-actions-zulip/send-message@v1
      with:
         api-key: ${{ secrets.ZULIP_API_KEY }}
         email: "username@example.com" # email address corresponding to the API key
         organization-url: "https://your-org.zulipchat.com"
         to: "9" # user_id
         type: "private"
         content: "With mirth and laughter let old wrinkles come." # Markdown message{%endraw%}
      ```

{end_tabs}

### Related documentation

* [Zulip GitHub Actions repository][repo]

* [Configuring the Send Message Action][README]

* [GitHub integration](/integrations/doc/github)

[README]: https://github.com/zulip/github-actions-zulip/blob/main/send-message/README.md
[repo]: https://github.com/zulip/github-actions-zulip
