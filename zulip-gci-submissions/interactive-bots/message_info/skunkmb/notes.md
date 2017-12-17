# `skunkmb`'s Notes
**(for *Learn about interactive bots, pt 2: creating a message info bot*)**

I encountered a few problems when working on this task, but it was an exciting
and educational experience.

## 1. Python 2 or Python 3?

The first problem I encountered was that I didn't know whether to use Python
Version 2 or 3 when creating my bot. I started [this conversation in the # CGI
Tasks stream] and got the answer back that I should be working in Python 3.

I also wanted to prevent future Zulip contributors from having the same
problem, so I made a [pull request clearing up that Python 3 should be used].
It got approved!

## 2. Weird Website Errors

After I wrote my bot, I started getting lots of error messages from the Zulip
developer website at skunkmb.zulipdev.org:9991. I [asked my mentors about
them], but I still wasn't able to get it fixed. Eventually, I switched from the
Remote VM to the local Vagrant dev environment, which worked great.

## 3. Some Testing Errors

Lastly, when I went to test my bot using `./tools/test-bots` I continuously got
errors telling me that there was `No module named mock`. However, when I ran
`pip install mock` it told me it was already installed. Eventually I realized
that I had to run `./tools/test-bots` in Python 3 in order for it to find the
`mock` module. When I ran `python3 ./tools/test-bots`, it worked!

[this conversation in the # CGI Tasks stream]: https://goo.gl/e4Bupg
[pull request clearing up that Python 3 should be used]: https://goo.gl/Bb2rMB
[asked my mentors about them]: https://goo.gl/K22PG3
