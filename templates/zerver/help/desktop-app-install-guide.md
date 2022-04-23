# Installing the Zulip desktop app

Zulip on your macOS, Windows, or Linux desktop is even better than
Zulip on the web, with a cleaner look, tray/dock integration, native
notifications, and support for multiple Zulip accounts.

To install the latest stable release (recommended for most users),
find your operating system below.  If you're interested in an early
look at the newest features, consider the [beta releases](#install-a-beta-release).

## Install the latest release

{start_tabs}
{tab|mac}

#### DMG or zip (DMG recommended)
<!-- TODO why zip? -->

1. Download and run [Zulip-x.x.x.dmg][latest] or [Zulip-x.x.x-mac.zip][latest].

2. Open or unzip the file, and drag the app into the `Applications` folder.

The app will update automatically to future versions.

#### Homebrew

1. Run `brew cask install zulip` in Terminal.

2. Zulip will be installed in `Applications`. <!-- TODO fact check -->

The app will update automatically to future versions. (`brew update && brew upgrade zulip` will also work, if you 
prefer)

{tab|windows}

#### Web installer (recommended)

1. Download and run [Zulip for Windows](https://zulip.com/apps/windows).

2. Run Zulip from the Start menu.

The app will update automatically to future versions.

#### Offline Portable  installer (for isolated networks)

1. Download [zulip-x.x.x-x64.nsis.7z][latest] for 64-bit desktops
   (common), or [zulip-x.x.x-ia32.nsis.7z][latest] for 32-bit (rare).

2. Copy the installer file to the machine you want to install the app
   on, extract, and run it there.

3. Run Zulip from the Start menu.

The app will NOT update automatically. You can repeat these steps to upgrade
to future versions. <!-- TODO fact check -->

{tab|linux}

#### APT (Ubuntu or Debian 8+)

1. Download [Zulip-x.x.x-amd64.deb][latest]

2. Double click and install, then run `zulip` in terminal.

	or

1. Enter the following commands into a terminal:

        sudo curl -fL -o /etc/apt/trusted.gpg.d/zulip-desktop.asc \
            https://download.zulip.com/desktop/apt/zulip-desktop.asc
        echo "deb https://download.zulip.com/desktop/apt stable main" | \
            sudo tee /etc/apt/sources.list.d/zulip-desktop.list
        sudo apt update
        sudo apt install zulip

    These commands set up the Zulip Desktop APT repository and its signing
    key, and then install the Zulip client.

2. Run Zulip from your app launcher.

The app will be updated automatically to future versions when you do a
regular software update on your system, e.g. with
`sudo apt update && sudo apt upgrade`.

#### AppImage (recommended for all other distros)

1. Download [Zulip for Linux](https://zulip.com/apps/linux).

2. Make the file executable, with
   `chmod a+x Zulip-x.x.x-x86_64.AppImage` from a terminal (replace
   `x.x.x` with the actual name of the downloaded file).

3. Run the file from your app launcher, or from a terminal.

No installer is necessary; this file is the Zulip app. The app will update
automatically to future versions.

#### Snap

1. Make sure [snapd](https://docs.snapcraft.io/core/install) is installed.

2. Execute following command to install Zulip:

        sudo snap install zulip

3. Run Zulip from your app launcher, or with `zulip` from a terminal.

<!-- TODO why dpkg? -->

{end_tabs}

## Install a beta release

Get a peek at new features before they're released!

#### macOS, Windows, and most Linux distros

Start by finding the latest version marked "Pre-release" on the
[release list page][release-list].  There may or may not be a "Pre-release"
later than the latest release. If there is, download the appropriate Zulip
installer or app from there, and follow the instructions for your operating
system above.

#### Linux with Apt-get (Ubuntu or Debian 8+)

1. First download the following signing key to ensure the deb download is correct:

```sudo apt-key adv --keyserver pool.sks-keyservers.net --recv 69AD12704E71A4803DCA3A682424BE5AE9BD10D9```

2. Then add the repo to the apt source list using the command

```echo "deb https://dl.bintray.com/zulip/debian/ beta main"
sudo tee -a /etc/apt/sources.list.d/zulip.list 
```

3. Install the client:
```
sudo apt-get update
sudo apt-get install zulip
```

[latest]: https://github.com/zulip/zulip-desktop/releases/latest
[release-list]: https://github.com/zulip/zulip-desktop/releases

## Related articles

* [Connect through a proxy](/help/connect-through-a-proxy)
* [Use a custom certificate](/help/custom-certificates)
* [View Zulip version](/help/view-zulip-version)
