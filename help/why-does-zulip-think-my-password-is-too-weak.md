# Why does Zulip think my password is too weak?

Zulip uses the [zxcvbn](https://github.com/dropbox/zxcvbn) password strength estimator, which analyzes your password and estimates how long it would take a modern password cracker to guess it.

If zxcvbn estimates that your password could be cracked in less than a few hours (by default), Zulip will reject it to keep your account safe. Server administrators may configure this threshold.

### Why zxcvbn might reject your password

zxcvbn looks for common patterns, such as:
- Dictionary words
- Leetspeak (e.g., "h@ck3r", "d0nth4ckMe")
- Keyboard patterns (e.g., "qwerty")
- Repetitive characters (e.g., "aaa111")
- Common names, years, or pop culture references

Even if you think your password is unique, if it follows one of these patterns, it may still be easy to crack.

### Tips for creating a strong password
- Use a **passphrase** made of unrelated words (e.g., "correct horse battery staple")
- Avoid using **dictionary words** or **personal information**
- Consider using a **password manager** like 1Password or Bitwarden
- **Never reuse passwords** across different websites

![xkcd password comic](https://imgs.xkcd.com/comics/password_strength.png)
[View comic source](https://xkcd.com/936/)

> 💡 Even if zxcvbn thinks your password is strong, it’s still important to follow best practices like not reusing passwords.

