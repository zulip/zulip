# Installing the Zulip desktop app

Zulip on your macOS, Windows, or Linux desktop is even better than
Zulip on the web, with a cleaner look, tray/dock integration, native
notifications, and support for multiple Zulip accounts.

To install the latest stable release (recommended for most users),
find your operating system below.  If you're interested in an early
look at the newest features, consider the [beta releases](#install-a-beta-release).

[LR]: https://github.com/zulip/zulip-desktop/releases

## Install the latest release

{start_tabs}
{tab|mac}

#### DMG or zip:

1. Download [Zulip-x.x.x.dmg][LR] or [Zulip-x.x.x-mac.zip][LR]
2. Open or unzip the file and drag the app into the `Applications` folder
3. Done! The app will update automatically

#### Using Homebrew:

1. Run `brew cask install zulip` in your terminal
2. The app will be installed in your `Applications`
3. Done! The app will update automatically (you can also use `brew update && brew upgrade zulip`)

{tab|windows}

#### Installer (recommended):

1. Download [Zulip-Web-Setup-x.x.x.exe][LR]
2. Run the installer, wait until it finishes
3. Done! The app will update automatically

#### Portable:

1. Download [zulip-x.x.x-arch.nsis.7z][LR]  [*here arch = ia32 (32-bit), x64 (64-bit)*]
2. Extract the zip wherever you want (e.g. a flash drive) and run the app from there

#### Offline installer (for isolated networks)

1. Download [zulip-x.x.x-x64.nsis.7z][latest] for 64-bit desktops
   (common), or [zulip-x.x.x-ia32.nsis.7z][latest] for 32-bit (rare).
2. Copy the installer file to the machine you want to install the app
   on, and run it there.
3. Run Zulip from the Start menu.

The app will NOT update automatically. You can repeat these steps to upgrade
to future versions. <!-- TODO fact check -->

{tab|linux}

#### Ubuntu, Debian 8+ (deb package):

1. Download [Zulip-x.x.x-amd64.deb][LR]
2. Double click and install, or run `dpkg -i Zulip-x.x.x-amd64.deb` in the terminal
3. Start the app with your app launcher or by running `zulip` in a terminal
4. Done! The app will NOT update automatically, but you can still check for updates

**Other distros (Fedora, CentOS, Arch Linux etc)** :
1. Download Zulip-x.x.x-x86_64.AppImage[LR]
2. Make it executable using chmod a+x Zulip-x.x.x-x86_64.AppImage
3. Start the app with your app launcher

**You can also use `apt-get` (recommended)**:

* First download our signing key to make sure the deb you download is correct:

```
sudo apt-key adv --keyserver pool.sks-keyservers.net --recv 69AD12704E71A4803DCA3A682424BE5AE9BD10D9
```

* Add the repo to your apt source list :
```
echo "deb https://dl.bintray.com/zulip/debian/ beta main" |
  sudo tee -a /etc/apt/sources.list.d/zulip.list
```

* Now install the client :
```
sudo apt-get update
sudo apt-get install zulip
```

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

#### Linux with apt (Ubuntu or Debian 8+)

If installing from scratch, follow the instructions above, except in the
command starting `echo "deb https://...` replace `stable` with `beta`.

If you've already installed the stable version, edit `zulip.list` and
reinstall:
```
sudo sed -i s/stable/beta/ /etc/apt/sources.list.d/zulip.list
sudo apt update
sudo apt install zulip
```
**Note:** If you download from the [releases page](https://github.com/zulip/zulip-desktop/releases), be careful what version you pick. Releases that end with `-beta` are beta releases and the rest are stable.
- **beta:** these releases are the right balance between getting new features early while staying away from nasty bugs.
- **stable:** these releases are more thoroughly tested; they receive new features later, but there's a lower chance that things will go wrong.

[latest]: https://github.com/zulip/zulip-desktop/releases/latest
[release-list]: https://github.com/zulip/zulip-desktop/releases

## Related articles

* [Connect through a proxy](/help/connect-through-a-proxy)
* [Use a custom certificate](/help/custom-certificates)

