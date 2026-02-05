# Presenting visual changes

If your pull request makes visual changes, or includes refactoring that might
cause visual changes, you must include screenshots demonstrating the impact of
your changes in the description for your pull request.

**Always make sure the screenshots in the PR description capture the _current_
state of the PR.** To avoid confusion, delete outdated screenshots from the
description. If reviewers need to see multiple variants of the UI to make some
decision, include those variants in the comments.

## What to capture

Always include screenshots of _all_ the UI components and states affected by
your PR. For example, a PR that adds a new dropwdown setting would need
screenshots to demonstrate:

- What the setting looks like in the settings UI (with some surrounding context).
- The open dropdown.
- The disabled version of the setting with its accompanying tooltip that would
  be shown to users who aren't allowed to modify the setting.
- Visual impact of using each value of the setting (if any).
- Updated help center documentation (if any); see
  [note](#presenting-documentation-changes) below.

If you're using standard components, there's no need to go overboard with
screenshots:

- Show the Before state if it provides helpful context (e.g., if you're changing
  text on a banner), but otherwise you can skip them (e.g., if you're adding a
  setting).
- There's usually no need to show light and dark theme screenshots, or
  screenshots at different font sizes.
- There's usually no need to show the keyboard selection UI.

However, if your pull request makes any CSS changes, you'll need to thoroughly
demonstrate its effects. You will need to **capture precise screenshots**
demonstrating the differences between the Before and After states, as described
[below](#capturing-precise-screenshots).

Precise screenshots are necessary not only to document your intended
changes, but also to demonstrate that there are **no unintended side-effects**
or visual regressions. In fact, PRs that refactor templates or CSS often need to
include screenshots to explicitly demonstrate that there are no visual changes.

:::{important}
Wherever possible, use still screenshots rather than videos.
:::

Static screenshots are much easier to review than screencast videos. Use a video
only when necessary to demonstrate an interaction, and only to supplement still
screenshots. Always include screenshots for any aspects of your changes which
can be seen on a still screenshot. See
[below](#capturing-and-presenting-short-videos) for how to capture reviewable videos.

For updates or changes to CSS class rules, it's a good practice
to include the results of a [git-grep][git-grep] search for
the class name(s) to confirm that you've tested and captured screenshots
of all the impacted areas of the UI or Zulip documentation.

```console
$ git grep '.example-class-name' web/templates/ templates/
templates/corporate/...
templates/zerver/...
web/templates/...
```

Never include screenshots of your code or the GitHub UI, which reviewers can
easily see directly.

## What are precise Before/After screenshots?

Precise Before/After screenshots have two essential qualities:

1. **The state of the UI should be identical between screenshots.**
   For example, a screenshot of the message feed should have messages scrolled to the
   same spot, the focus ring should be around the same message, etc. The goal is to
   highlight the differences your PR introduces, and not include any unintended noise in
   the screenshots from things that just happen to be different.
1. **The screenshots must have the exact same pixel dimensions.** If the Before
   screenshot is 800px by 600px, the After screenshot should be too. This is
   to make sure that there's a pixel-to-pixel correspondence of everything
   you've captured onscreen.

## Why bother with precise Before/After screenshots?

Capturing precise screenshots serves two primary purposes:

1. For you as a contributor, **checking your own screenshots** will help you to
   catch any regressions on your own, prior to submitting your PR. It'll also
   help you point out changes or shifts for reviewers to consider, which may
   require some design discussion.
2. For reviewers, checking screenshots is a quick way to **verify** that a PR
   does what's expected, and provide **feedback** on visual changes without
   pulling down the PR.

## Capturing precise screenshots

This section describes different techniques for producing pixel-precise
screen captures. To master these techniques, you'll likely need to spend some time
working with your capture tools of choice, whether they're part of your browser or
operating system, or a third-party screen capture tool or browser plugin.

### Using Git to get required states

Git is, of course, your friend for setting up the UI state for Before and After
screenshots: the Before shot will typically be of the `main` branch updated from
upstream, while the After shot will be of your PR's working branch. Take the time
to rebase your working branch over the latest `main`, too, before capturing your
screenshots.

Sometimes you may be asked to present alternative looks to your PR in tandem
with a discussion [#design](https://chat.zulip.org/#topics/channel/101-design)
channel in the Zulip development community, in which case you'll need to walk
through different commits on your branch—or make judicious use of `git stash`
and `git stash pop`.

### Capturing precise screenshots with your browser

The easiest cross-platform way of capturing screenshots of your PR's changes
is to use your browser. Both Chrome and Firefox have built-in screenshot capabilities,
so it's worth your time to explore how those work. Firefox's capabilities are neatly
tied to its responsive design view, which means you can very precisely size the viewport
to highlight the changes in your PR. (And if you're not used to developing in Firefox,
this can be a convenient way to check your work in a different browser, too.)

For example, it's easy to capture a mobile-scale viewport in Firefox like this:

| In responsive mode for capture                                               | Resulting screenshot                                                           |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| ![Firefox in responsive design mode](/images/firefox-rwd-capture-mobile.png) | ![Mobile-scale capture from Firefox](/images/firefox-mobile-scale-350x600.png) |

For another example, if you're making changes to the left sidebar, you'll want to open
the viewport wider, until the left sidebar is showing:

![Firefox in opened wider to show sidebar](/images/firefox-rwd-capture-medium.png)

The great thing about capturing screenshots in your browser is that it is very easy to ensure that you meet both criteria for precise screenshots: a UI in the same state for
the Before and After shots, and screenshots that are the same exact dimensions—easily verified by the values you set on the width and height of the viewport.

Additionally, if you need to demonstrate states like `:hover` or `:active` on an element,
you can use your browser's developer tools to emulate that state for you, without your
needing to fiddle with the keyboard or mouse.

### Capturing precise screenshots with native OS tools

Most of the time, browser-captured screenshots are ideal. Screens are generally
high-enough resolution that your reviewers (and you) can quickly recognize any
changes just by comparing the full-size screenshots.

However, if you really do need to illustrate a change in closer detail, it can be helpful
to use your operating system's native screen-capture tools. See if your OS allows
you to specify a box of fixed dimensions that you can use to repeatedly capture the same
area of the screen.

For example, perhaps there's something very subtle about the channel list that a PR needs
to highlight:

![Fixed region capture using OS tools](/images/os-fixed-capture-box.png)

Note that [a fixed, reusable capture box is different from a freehand capture](#freehand-versus-fixed-screenshots),
because the OS enables you to call up the same fixed-size box for repeated screenshots
of the same region of the screen, helping you to maintain pixel precision in the
Before and After shots. Just be careful not to move your browser window around between
shots.

### Capturing precise screenshots with other software

If you find that your operating system or browser's tools are insufficient for capturing
the screenshots that you need, you might want to explore [third-party software](#screenshot-and-gif-software). Just keep
in mind the two qualities your screenshots need to maintain: identical UI state, and
pixel-precise dimensions between Before and After shots.

### Freehand versus fixed screenshots

It may be tempting to freehand your screenshots, perhaps by using your operating
system's screen-capture utility that allows freehand dragging of a capture area.
The two freehand-captured images below represent Before and After states. Can you
spot any changes to the UI? How about if you open each image in a separate tab in
your browser? (Typically a reviewer will open up the full-size images in separate
tabs in order to more easily compare them.)

| Before                                                          | After                                                         |
| --------------------------------------------------------------- | ------------------------------------------------------------- |
| ![Freehand screenshot, before](/images/freehand-cap-before.png) | ![Freehand screenshot, after](/images/freehand-cap-after.png) |

Here's an animated GIF approximating a comparison of the full-size images:

![Comparing freehand screenshots](/images/freehand-capture-compare.gif)

Compare those to this set of screenshots. These are the same Before and After
states as captured in the freehand shots above, but these have been captured using
a fixed box offered by an operating system's native screen-capture utility:

| Before                                                    | After                                                   |
| --------------------------------------------------------- | ------------------------------------------------------- |
| ![Fixed screenshot, before](/images/fixed-cap-before.png) | ![Fixed screenshot, after](/images/fixed-cap-after.png) |

Now see if you can catch the change between the Before and After images in this GIF:

![Comparing fixed screenshots](/images/fixed-capture-compare.gif)

Those screenshots make it obvious that the space between the Zulip logo and the top
of the message area has been reduced. Without precise screenshots, that change
would've been nearly impossible to detect.

### Providing sufficient UI context

The images above might have been intended to show close details of the Zulip logo
and message area. But the contributor could have also just used their browser
(Firefox, in this case) to capture more of the viewport:

| Before                                                            | After                                                           |
| ----------------------------------------------------------------- | --------------------------------------------------------------- |
| ![Browser screenshot, before](/images/browser-capture-before.png) | ![Browser screenshot, after](/images/browser-capture-after.png) |

Even if your work is targeted at a specific element, detailed screenshots are not
always the best choice. CSS adjustments are notorious for having unintended consequences,
so it's often a smart choice to show as much of the UI as you can.

As with the fixed-box screenshots above, having pixel-precise screenshots
where the UI is in an identical state and there isn't a bunch of unintended movement
or other noise, the browser captures above make catching the space shift much easier.

## Capturing and presenting short videos

Still screenshots are almost always superior to videos. They are easier to compare, and
enable reviewers to focus more precisely on the changes your PR introduces.

If you absolutely must show off a brief interaction on your PR, see whether your operating
system will allow you to again set a fixed box for capturing video of a region of your
screen.

Be sure to edit your video down to the shortest length possible. And rather
than post the video—whose format may not be suitable for the web or accessible to all
reviewers—use a video-to-GIF service like [ezgif.com](https://ezgif.com/video-to-gif)
to create a looping animation showing off the interaction.

Here, for an example, is a short looping animation from [an actual PR](https://github.com/zulip/zulip/pull/35969)
that modified some interactions on the compose box:

![Animation showing compose box](/images/general-chat-after.gif)

It's worth noting here that [the full PR](https://github.com/zulip/zulip/pull/35969)
included plenty of static screenshots in addition to the GIFs showing off interactivity.

Finally, make sure a person watching your video can see where on the screen you're
tapping or clicking. Use the "show touches" or "include the mouse pointer" feature
if your screen-recording software supports it.

## Presenting screenshots on your pull request

Now that you've got all these screenshots, how do you present them in the
description for your PR?

### Using tables for Before/After comparisons

For presenting Before and After states, use GitHub's table syntax to render
them side-by-side. Reviewers can open the full-size image from GitHub for quick
and easy comparison:

```
### Descriptive header for images:

| Before | After |
| --- | --- |
| ![image-before](uploaded-file-information) | ![image-after](uploaded-file-information)
```

To quickly insert these tables, consider
[creating a GitHub Saved Reply](https://docs.github.com/en/get-started/writing-on-github/working-with-saved-replies/creating-a-saved-reply).

### Making screenshots collapsible

When including numerous screenshots or screencasts, consider grouping them
in details/summary tags to reduce visual clutter and the scroll length of
pull-request descriptions and comments. This is especially useful when you
have several screenshots or screencasts to include in your PR description
or follow-up comments, as you can put groups of related images in separate
details/summary tags.

Do think about your reviewers' comfort when using more than one set of
details/summary tags, as it is generally much easier to scroll past a
bunch of screenshots than it is to open numerous collapsed details/summary
tags.

```
<details>
<summary>Descriptive summary of image group</summary>

| Before | After |
| --- | --- |
| ![image-before](uploaded-file-information) | ![image-after](uploaded-file-information) |
| ![image-2-before](uploaded-file-information) | ![image-2-after](uploaded-file-information) |

</details>
```

### Presenting documentation changes

If you've updated existing documentation in your pull request,
include a link to the current documentation above the screenshot
of the updates. That way a reviewer can quickly compare the current
documentation while reviewing your changes.

```
[Current documentation](link-to-current-documentation-page)
![image-after](uploaded-file-information)
```

[git-grep]: https://git-scm.com/docs/git-grep
[screenshots-gifs]: ../contributing/presenting-visual-changes.md#screenshot-and-gif-software
[zulip-dev-community]: https://chat.zulip.org
[link-to-message]: https://zulip.com/help/link-to-a-message-or-conversation#get-a-link-to-a-specific-message
[dev-community-linkifiers]: https://zulip.com/development-community/#linking-to-github-issues-and-pull-requests

## Screenshot and GIF software

You can check out the following tools for capturing screenshots and videos/GIFs.

### Screenshot tools by platform

#### Browser

- [Firefox screenshots](https://support.mozilla.org/en-US/kb/take-screenshots-firefox) without any plugins
- [Chrome screenshots](https://developer.chrome.com/docs/devtools/device-mode#screenshot) without any plugins
- [LightShot Screenshot](https://app.prntscr.com/en/index.html) (Chrome, Firefox, IE & Opera)
- [Chrome Capture](https://chrome.google.com/webstore/detail/chrome-capture-screenshot/ggaabchcecdbomdcnbahdfddfikjmphe?hl=en)

#### macOS

- [Take a screenshot on Mac](https://support.apple.com/en-us/102646)
- [LightShot Screenshot](https://app.prntscr.com/en/index.html)
- [Gyazo](https://gyazo.com/en)

#### Windows

- [Use Snipping Tool to capture screenshots](https://support.microsoft.com/en-us/windows/use-snipping-tool-to-capture-screenshots-00246869-1843-655f-f220-97299b865f6b)
- [LightShot Screenshot](https://app.prntscr.com/en/index.html)
- [Gyazo](https://gyazo.com/en)
- [ScreenToGif](https://www.screentogif.com/)

#### Linux

- [GNOME Screenshots and screencasts](https://help.gnome.org/gnome-help/screen-shot-record.html)
- [Spectacle by KDE](https://apps.kde.org/spectacle/)

### GIF tools by platform

#### Browser

- [GIPHY](https://giphy.com)
- [Chrome Capture](https://chrome.google.com/webstore/detail/chrome-capture/ggaabchcecdbomdcnbahdfddfikjmphe?hl=en)
  (Tip: Use `Alt`+`I` to interact with the page while recording)

#### macOS

- [QuickTime](https://support.apple.com/en-in/HT201066)
- [GIPHY](https://giphy.com/apps/giphycapture)
- [Zight](https://zight.com)
- [Kap](https://getkap.co)
- [Gifski](https://sindresorhus.com/gifski)
- [Gyazo GIF](https://gyazo.com/en)

#### Windows

- [ScreenToGif](https://www.screentogif.com)
- [Gyazo GIF](https://gyazo.com/en)

#### Linux

- [Peek](https://github.com/phw/peek)
- [SilentCast](https://github.com/colinkeenan/silentcast)
