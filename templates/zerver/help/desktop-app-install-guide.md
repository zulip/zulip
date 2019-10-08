# Installing the Zulip desktop app

Zulip on your macOS, Windows, or Linux desktop is even better than
Zulip on the web, with a cleaner look, tray/dock integration, native
notifications, and support for multiple Zulip accounts.

To install the latest stable release (recommended for most users),
find your operating system below.  If you're interested in an early
look at the newest features, consider the [beta releases](#beta-releases).

{start_tabs}
{tab|mac}

### Disk image (recommended)
<!-- TODO why zip? -->

1. Download [Zulip for macOS](https://zulipchat.com/apps/mac).
1. Open the file, and drag the app into the `Applications` folder.

The app will update automatically to future versions.

### Homebrew

1. Run `brew cask install zulip` in Terminal.
1. Run Zulip from `Applications`. <!-- TODO fact check -->

The app will update automatically to future versions. `brew upgrade` will
also work, if you prefer.

{tab|windows}

### Web installer (recommended)

1. Download and run [Zulip for Windows](https://zulipchat.com/apps/windows).
1. Run Zulip from the Start menu.

The app will update automatically to future versions.

### Offline installer (for isolated networks)

1. Download [zulip-x.x.x-x64.nsis.7z][latest] for 64-bit desktops
   (common), or [zulip-x.x.x-ia32.nsis.7z][latest] for 32-bit (rare).
2. Copy the installer file to the machine you want to install the app
   on, and run it there.
3. Run Zulip from the Start menu.

The app will NOT update automatically. You can repeat these steps to upgrade
to future versions. <!-- TODO fact check -->

{tab|linux}

### apt (Ubuntu or Debian 8+)

1. Enter the following commands into a terminal:

        sudo apt-key adv --keyserver pool.sks-keyservers.net --recv 69AD12704E71A4803DCA3A682424BE5AE9BD10D9
        echo "deb https://dl.bintray.com/zulip/debian/ stable main" | \
        sudo tee -a /etc/apt/sources.list.d/zulip.list
        sudo apt update
        sudo apt install zulip

    These commands set up the Zulip Desktop apt repository and its signing
    key, and then install the Zulip client.

1. Run Zulip from your app launcher, or with `zulip` from a terminal.

The app will be updated automatically to future versions when you do a
regular software update on your system, e.g. with
`sudo apt update && sudo apt upgrade`.

### AppImage (recommended for all other distros)

1. Download [Zulip for Linux](https://zulipchat.com/apps/linux).
2. Make the file executable, with
   `chmod a+x Zulip-x.x.x-x86_64.AppImage` from a terminal (replace
   `x.x.x` with the actual name of the downloaded file).
3. Run the file from your app launcher, or from a terminal.

No installer is necessary; this file is the Zulip app. The app will update
automatically to future versions.

### Snap

1. Make sure [snapd](https://docs.snapcraft.io/core/install) is installed.

2. Execute following command to install Zulip:

        sudo snap install zulip

3. Run Zulip from your app launcher, or with `zulip` from a terminal.

<!-- TODO why dpkg? -->

{end_tabs}

## Beta releases

Get a peek at new features before they're released!

### macOS, Windows, and most Linux distros

Start by finding the latest version marked "Pre-release" on the
[release list page][release-list].  There may or may not be a "Pre-release"
later than the latest release. If there is, download the approriate Zulip
installer or app from there, and follow the instructions for your operating
system above.

### Linux with apt (Ubuntu or Debian 8+)

If installing from scratch, follow the instructions above, except in the
command starting `echo "deb https://...` replace `stable` with `beta`.

If you've already installed the stable version, edit `zulip.list` and
reinstall:
```
sudo sed -i s/stable/beta/ /etc/apt/sources.list.d/zulip.list
sudo apt update
sudo apt install zulip
```

[latest]: https://github.com/zulip/zulip-electron/releases/latest
[release-list]: https://github.com/zulip/zulip-electron/releases

## Related articles

* [Connect through a proxy](/help/connect-through-a-proxy)
* [Add a custom certificate](/help/custom-certificates)
