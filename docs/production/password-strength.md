---
orphan: true
---

# Password strength

When a user tries to set a password, we use [zxcvbn][zxcvbn] to check
that it isn't a weak one.

See discussion in [our main docs for server
admins](security-model.md#passwords). This doc explains in more
detail how we set the default threshold (`PASSWORD_MIN_GUESSES`) we use.

First, read the doc section there. (It's short.)

Then, the CACM article ["Passwords and the Evolution of Imperfect
Authentication"][bhos15] is comprehensive, educational, and readable,
and is especially recommended.

The CACM article is convincing that password requirements should be
set to make passwords withstand an online attack, but not an offline
one. Offline attacks are much less common, and there is a wide gap in
the level of password strength required to beat them vs that for
online attacks -- and therefore in the level of user frustration that
such a requirement would cause.

On top of that, estimating strength rapidly becomes more expensive
at high levels, in both space (for lists of tokens to try) and time.
As a result, in order to fit in a few MB of download and a few ms of
check time, zxcvbn focuses on the range of online attacks, for the
upper limit of which it uses 10^6 (apparently based on the offhand
estimate of "perhaps one million guesses" in the CACM article.)

Figure 3 of [the zxcvbn paper][zxcvbn-paper] shows that in fact
overestimation (allowing a weak password) sharply degrades at 100k
guesses, while underestimation (rejecting a strong password) jumps up
just after 10k guesses, and grows steadily thereafter.

Moreover, the [Yahoo study][bon12] shows that resistance to even 1M
guesses is more than nearly half of users accomplish with a freely
chosen password, and 100k is too much for about 20%. (See Figure 6.)
It doesn't make sense for a Zulip server to try to educate or push so
many users far beyond the security practices they're accustomed to; in
the few environments where users can be expected to work much harder
for security, local server admins can raise the threshold accordingly.
Or, more likely, they already have a single-sign-on system in use for
most everything else in their organization, and will disable password
auth in Zulip entirely in favor of using that.

Our threshold of 10k guesses provides significant protection against
online attacks, and quite strong protection with appropriate
rate-limiting. On the other hand it stays within the range where
zxcvbn rarely underestimates the strength of a password too severely,
and only about 10% of users do worse than this without prompting.

[zxcvbn]: https://github.com/dropbox/zxcvbn
[bhos15]: https://www.cl.cam.ac.uk/~fms27/papers/2015-BonneauHerOorSta-passwords.pdf
[zxcvbn-paper]: https://www.usenix.org/system/files/conference/usenixsecurity16/sec16_paper_wheeler.pdf
[bon12]: https://ieeexplore.ieee.org/document/6234435
