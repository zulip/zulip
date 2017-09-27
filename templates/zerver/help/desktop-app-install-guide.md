# How to install Desktop app

[LR]: https://github.com/zulip/zulip-electron/releases/latest

If you download from the [releases page][LR], be careful what version you pick.
There are two versions available -

- **beta:** these releases are the right balance between getting
    new features early while staying away from nasty bugs.
- **stable:** these releases are more thoroughly tested; they receive
    new features later, but there's a lower chance that things will go wrong.

## Mac

**DMG or zip**:

1. Download [Zulip-x.x.x.dmg][LR] or [Zulip-x.x.x-mac.zip][LR]
2. Open or unzip the file and drag the app into the `Applications` folder
3. Done! The app will update automatically

**Using brew**:

1. Run `brew cask install zulip` in your terminal
2. The app will be installed in your `Applications`
3. Done! The app will update automatically (you can also use `brew update && brew upgrade zulip`)

## Windows

**Installer (recommended)**:

1. Download [Zulip-Web-Setup-x.x.x.exe][LR]
2. Run the installer, wait until it finishes
3. Done! The app will update automatically

**Portable**:

1. Download [zulip-x.x.x-arch.nsis.7z][LR]  [*here arch = ia32 (32-bit), x64 (64-bit)*]
2. Extract the zip wherever you want (e.g. a flash drive) and run the app from there

## Linux

**Ubuntu, Debian 8+ (deb package)**:

1. Download [Zulip-x.x.x-amd64.deb][LR]
2. Double click and install, or run `dpkg -i Zulip-x.x.x-amd64.deb` in the terminal
3. Start the app with your app launcher or by running `zulip` in a terminal
4. Done! The app will NOT update automatically, but you can still check for updates

**Other distros (Fedora, CentOS, Arch Linux etc)** :

1. Download [Zulip-x.x.x-x86_64.AppImage][LR]
2. Make it executable using `chmod a+x Zulip-x.x.x-x86_64.AppImage`
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
