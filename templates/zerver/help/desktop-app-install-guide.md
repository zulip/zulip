# Installing the Zulip desktop app

Zulip on your macOS, Windows, or Linux desktop is even better than
Zulip on the web, with a cleaner look, tray/dock integration, native
notifications, and support for multiple Zulip accounts.

To install the latest stable release (recommended for most users),
find your operating system below.  If you're interested in an early
look at the newest features, consider the [beta releases](#beta-releases).

<!-- This heading is linked to directly from /apps; change with caution -->
## Installing on macOS

### Disk image (recommended)
<!-- TODO why zip? -->

1. Download [Zulip-x.x.x.dmg][latest]
2. Open the file, and drag the app into the `Applications` folder
3. Done!
4. The app will update automatically to future versions.

### Homebrew

If you have Homebrew installed and prefer to use it, here's how.

1. Run `brew cask install zulip` in your terminal
2. Done! Run Zulip from `Applications`. <!-- TODO fact check -->
3. The app will update automatically to future versions.
   (`brew upgrade` will also work, if you prefer.)

<!-- This heading is linked to directly from /apps; change with caution -->
## Installing on Windows

### Installer (recommended)

1. Download and run [Zulip-Web-Setup-x.x.x.exe][latest]
2. The installer will download and install the app.
3. Done! Run Zulip from the Start menu.
4. The app will update automatically to future versions.

### Offline installer (for isolated networks)

1. Download [zulip-x.x.x-x64.nsis.7z][latest] for 64-bit desktops
   (common), or [zulip-x.x.x-ia32.nsis.7z][latest] for 32-bit (rare).
2. Copy the installer file to the machine you want to install the app
   on, and run it there.
3. Done! Run Zulip from the Start menu.
4. The app will NOT update automatically. You can repeat these steps
   to upgrade to future versions. <!-- TODO fact check -->

<!-- This heading is linked to directly from /apps; change with caution -->
## Installing on Linux

### apt (recommended for Ubuntu or Debian 8+)

1. Set up the Zulip Desktop apt repository and its signing key, from a
   terminal:

        sudo apt-key adv --keyserver pool.sks-keyservers.net --recv 69AD12704E71A4803DCA3A682424BE5AE9BD10D9
        echo "deb https://dl.bintray.com/zulip/debian/ stable main" | \
        sudo tee -a /etc/apt/sources.list.d/zulip.list

2. Install the client, from a terminal:

        sudo apt update
        sudo apt install zulip

3. Done! Run Zulip from your app launcher, or with `zulip` from a
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

<!-- TODO why dpkg? -->

# Beta releases

Get a peek at new features before they're released!  If you'd like to
be among the first to get new features in the Zulip desktop app, and
to give the Zulip developers feedback to help make each stable release
the best it can be, then you might like the beta releases.

## Installing on macOS, Windows, or Linux with AppImage

Start by finding the latest version marked "Pre-release" on the
[release list page][release-list].  Then follow the instructions
above, except download the Zulip installer or app from that version
instead of from the latest stable release.

## Installing on Linux with apt

Follow the instructions above, except in the step involving
`/etc/apt/sources.list.d/zulip.list`, write "beta" instead of
"stable".

If you already have the stable version installed: edit that file, with
this command in a terminal:
```
sudo sed -i s/stable/beta/ /etc/apt/sources.list.d/zulip.list
```
and repeat the next step:
```
sudo apt update
sudo apt install zulip
```


[latest]: https://github.com/zulip/zulip-electron/releases/latest
[release-list]: https://github.com/zulip/zulip-electron/releases
