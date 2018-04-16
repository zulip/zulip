# Using Zulip on Linux

Zulip on the Linux desktop is even better than Zulip on the web,
with a cleaner look, native notifications, and support for multiple Zulip accounts.

## Download Instructions

### apt (recommended for Ubuntu or Debian 8+)

1. Set up the Zulip Desktop apt repository and its signing key, from a
   terminal:

```
sudo apt-key adv --keyserver pool.sks-keyservers.net --recv 69AD12704E71A4803DCA3A682424BE5AE9BD10D9
echo "deb https://dl.bintray.com/zulip/debian/ stable main" | \
  sudo tee -a /etc/apt/sources.list.d/zulip.list
```

2. Install the client, from a terminal:
```
sudo apt update
sudo apt install zulip
```

3. Now, you can run Zulip from your app launcher, or with `zulip` from a
   terminal.
4. The app will be updated automatically to future versions when
   you do a regular software update on your system, e.g. with
   `sudo apt update && sudo apt upgrade`.

### AppImage (recommended for all other distros)

1. Download [Zulip-x.x.x-x86_64.AppImage][latest]
2. Make the file executable, with
   `chmod a+x Zulip-x.x.x-x86_64.AppImage` from a terminal.
3. Done! No installer necessary; this file is the Zulip app.  Run it
   from your app launcher, or from a terminal.
3. The app will NOT update automatically. You can repeat these steps
   to upgrade to future versions.




## Initial setup

### Connecting to a server

When you open the Zulip desktop app for the first time, a screen asking
for your server's or organization's address will appear.
You have to write the server's URL in it, and press **Save**.

!!! warn ""
    **Note:** There's no need to add `https://` in case your server is running a secure
    HTTP (HTTPS) protocol.

    However, if your server uses an insecure HTTP connection, you'll have to
    write `http://` manually before the server's URL. A message will appear,
    warning you about the risks
    of using this type of connections. In case you have no other choice, choose the
    **Use HTTP** option.

### Logging in

After connecting to the server, you'll be able to log in either with an email
address and a password, or using your Google or GitHub account.

* If you decide to log in with an email/password combination, enter your email
address in the **Email** field and your password in the **Password** field,
then press **Sign in**.
* If you prefer to log in with your Google or GitHub account,
then press the **Sign in with Google** or **Sign in with GitHub** button.

    ![Login form](/static/images/help/linux-log-in.png)

### Adding another server

To add another organization or server that you're part of,
select (+) icon from the left sidebar
and you can add the URL same way you did before.
