## Logging in

Once the import completes, all your users will have accounts in your
new Zulip organization, but those accounts won't have passwords yet
(since for very good security reasons, passwords are not exported).
Your users will need to either authenticate using something like
Google auth, or start by resetting their passwords.

You can use the `./manage.py send_password_reset_email` command to
send password reset emails to your users.  We
recommend starting with sending one to yourself for testing:

```
./manage.py send_password_reset_email -u username@example.com
```

and then once you're ready, you can email them to everyone using e.g.
```
./manage.py send_password_reset_email -r '' --all-users
```

(replace `''` with your subdomain if you're using one).
