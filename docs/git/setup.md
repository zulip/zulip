# Set up Git

If you're already using Git, have a client you like, and a GitHub account, you
can skip this section. Otherwise, read on!

## Install and configure Git, join GitHub

If you're not already using Git, you might need to [install][gitbook-install]
and [configure][gitbook-setup] it.

**If you are using Windows 10 without [WSL
2](https://docs.microsoft.com/en-us/windows/wsl/wsl2-about), make sure you
[are running Git BASH as an administrator][git-bash-admin] at all times.**

You'll also need a GitHub account, which you can sign up for
[here][github-join].

We highly recommend you create an SSH key if you don't already have
one and [add it to your GitHub account][github-help-add-ssh-key]. If
you don't, you'll have to type your GitHub username and password every
time you interact with GitHub, which is usually several times a day.

We also highly recommend the following:

- [Configure Git][gitbook-config] with your name and email and
  [aliases][gitbook-aliases] for commands you'll use often. We
  recommend using your full name (not just your first name), since
  that's what we'll use to give credit to your work in places like the
  Zulip release notes.
- Install the command auto-completion and/or git-prompt plugins available for
  [Bash][gitbook-other-envs-bash] and [Zsh][gitbook-other-envs-zsh].

If you are installing the Zulip development environment, now you are ready to
continue with [Step 1: Install prerequisites](../development/setup-recommended.md#step-1-install-prerequisites).

## Get a graphical client

Even if you're comfortable using Git on the command line, having a graphical
client can be useful for viewing your repository. This is especially true
when doing complicated rebases and similar operations because you can check
the state of your repository after each command to see what changed. If
something goes wrong, this helps you figure out when and why.

If you don't already have one installed, here are some suggestions:

- macOS: [GitX][gitgui-gitx] (previously [GitX-dev][gitgui-gitxdev])
- Ubuntu/Linux: [git-cola][gitgui-gitcola], [gitg][gitgui-gitg], [gitk][gitgui-gitk]
- Windows: [SourceTree][gitgui-sourcetree]

If you like working on the command line, but want better visualization and
navigation of your Git repo, try [Tig][tig], a cross-platform ncurses-based
text-mode interface to Git.

And, if none of the above are to your liking, try [one of these][gitbook-guis].

[git-bash-admin]: ../development/setup-advanced.md#running-git-bash-as-an-administrator
[gitbook-aliases]: https://git-scm.com/book/en/v2/Git-Basics-Git-Aliases
[gitbook-config]: https://git-scm.com/book/en/v2/Customizing-Git-Git-Configuration
[gitbook-guis]: https://git-scm.com/downloads/guis
[gitbook-install]: https://git-scm.com/book/en/v2/Getting-Started-Installing-Git
[github-join]: https://github.com/join
[gitbook-setup]: https://git-scm.com/book/en/v2/Getting-Started-First-Time-Git-Setup
[gitbook-other-envs-bash]: https://git-scm.com/book/en/v2/Appendix-A%3A-Git-in-Other-Environments-Git-in-Bash
[gitbook-other-envs-zsh]: https://git-scm.com/book/en/v2/Appendix-A%3A-Git-in-Other-Environments-Git-in-Zsh
[gitgui-gitcola]: https://git-cola.github.io/
[gitgui-gitg]: https://wiki.gnome.org/Apps/Gitg
[gitgui-gitk]: https://git-scm.com/docs/gitk
[gitgui-gitx]: https://github.com/gitx/gitx/
[gitgui-gitxdev]: https://rowanj.github.io/gitx/
[gitgui-sourcetree]: https://www.sourcetreeapp.com/
[github-help-add-ssh-key]: https://help.github.com/en/articles/adding-a-new-ssh-key-to-your-github-account
[tig]: https://jonas.github.io/tig/
