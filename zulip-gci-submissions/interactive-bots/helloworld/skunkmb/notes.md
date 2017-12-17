# `skunkmb`'s Notes
**(for *Learn about interactive bots, pt 1: running the helloworld bot*)**

The main problem I encountered, which I discussed in [this Zulip chat], was a
404 error when running the `zulip-run-bot` command.

I was able to set up the dev server, visit it through
http://skunkmb.zulipdev.org:9991, set up the bot account, and download the
`zuliprc` for it. However, when I ran
`zulip-run-bot helloworld --config-file ~/zuliprc`, I got the following error:

```
Error initializing state: {'result': 'http-error', 'msg': 'Unexpected error from the server', 'status_code': 404}
```

I tracked down the error to a 404 response specifically from
`/api/v1/user_state`. In a web browser, I opened
http://skunkmb.zulipdev.org:9991/api/v1/user_state and got a 404 as well. I
also tried `/api` and `/api/v1`. Both of those had valid responses, but not
`/api/v1/user_state`.

Eventually, I figured out that I needed to follow [the instructions for
installing a dev version of the Zulip bots package] in order to get it to work,
which was not a solution my mentors predicted.

---

Another, smaller issue was a difficulty in finding this very repo. [The
instructions for this task] said to add the information to the
`interactive-bots` folder, but I wasn't sure where that folder was because it
wasn't in the same repository as the instructions.

I scrolled down to see the later instruction about pull requests, and followed
that line in order to find the repo.

[The instructions for installing a dev version of the Zulip bots package]: https://zulipchat.com/api/writing-bots#installing-a-development-version-of-the-zulip-bots-package
[this Zulip chat]: (https://chat.zulip.org/#narrow/stream/GCI.20tasks/subject/Bots.20404.20Error/near/345968)
[the instructions for this task]: https://github.com/zulip/zulip-gci/blob/master/tasks/2017/interactive-bots.md#task-type-a-learn-about-interactive-bots-by-running-the-helloworld-bot
