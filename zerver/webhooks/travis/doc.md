See your Travis CI build notifications in Zulip!

{!create-stream.md!}

{!create-bot-construct-url.md!}

Finally, set up a webhook in your `.travis.yml` file:

```
notifications:
webhooks:
- {{ api_url }}/v1/external/travis?stream=travis&topic=build-status&api_key=abcdefgh
```

By default, pull request events are ignored since most people
don't want notifications for new pushes to pull requests.  To
enable notifications for pull request builds, just
add `&ignore_pull_requests=false` at the end of the URL.

{!congrats.md!}

![](/static/images/integrations/travis/001.png)
