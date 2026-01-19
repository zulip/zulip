# Documenting visual changes

PRs that touch Zulip's user interface must include precise screenshots
that document the Before and After states associated with the PR's changes.
Even if your PR doesn't modify Zulip's CSS, it is commonly the case that
template adjustments and changes to JavaScript that touch the DOM may cause
visual changes that must be documented as part of a successful PR. That
includes demonstrating that your PR introduces no changes whatsoever, which
is typical with refactoring and other code-quality work.

## Capturing precise screenshots

Precise sets of static screenshots take a little bit of effort to capture, but
are well worth your time to create, and your reviewers' time too.

:::{important}
**You might ask, "Why can't I just make a video showing my changes?"** The answer is
that static screenshots are much easier to compare than screencast videos. Whenever
possible, use still screenshots instead of videos. (If you absolutely must include
a video, you'll find guidance further down this page for doing so appropriately.)
:::

Git is, of course, your friend for setting up the UI state for Before and After screenshots: typically the Before shot will be of the `main` branch updated from
upstream, while the After shot will be of your PR's working branch. Take the time
to rebase your working branch over the latest `main`, too, before capturing your
screenshots.

Sometimes you may be asked to present alternative looks to your PR in tandem with a
discussion on CZO in the [#design](https://chat.zulip.org/#topics/channel/101-design)
channel, in which case you'll need to walk through different commits on your branch—or
make judicious use of `git stash` and `git stash pop`.

Precise sets of Before/After screenshots have two essential qualities:

1. **The state of the UI should be identical between screenshots.**
   For example, a screenshot of the message feed should have messages scrolled to the
   same spot, the focus ring should be around the same message, etc. The goal is to
   highlight the differences your PR introduces, and not include any unintended noise in
   the screenshots from things that just happen to be different.
1. **The screenshots must have the exact same pixel dimensions.** If the Before
   screenshot is 800px by 600px, the After screenshot should be too. This is
   to make sure that there's a pixel-to-pixel correspondence of everything
   you've captured onscreen.

The next sections describe different techniques for capturing pixel-precise
screen captures. To master these techniques, you'll likely need to spend some time
working with your capture tools of choice, whether they're part of your browser or
operating system, or a third-party screen capture tool or browser plugin. You should
also take the time to read about
[why precise screenshots matter](#why-precise-screenshots-matter).

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
the viewport even wider, until the left sidebar is showing:

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

### Capturing and presenting short videos

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

## Why precise screenshots matter

Precise screenshots are necessary not only to document your intended
changes, but also to demonstrate that there are no unintended side-effects
or visual regressions. In fact, PRs that refactor templates or CSS often
include screenshots to explicitly demonstrate that there are no visual changes.

Capturing precise screenshots serves two primary purposes:

1. For you as a contributor, checking your own screenshots will help you
   to catch any regressions on your own, prior to submitting your PR, or
   to point out changes or shifts for reviewers and possibly further design
   discussion.
2. For reviewers, checking screenshots is a very quick way to verify that
   a PR does what it intends without the reviewer needing to pull down the
   PR and check it more closely in development (though that is a routine
   part of reviewing as well).

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

## Screenshot and GIF software

The following list documents different free and open-source screenshot and GIF-making
software. We encourage you to make use of these when making front-end pull requests,
and to suggest tools that you use for inclusion here for the benefit of other contributors.

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

- gnome-screenshot (inbuilt, you can use Ctrl-Shift-PrtScn as a shortcut for its “select an area to grab” feature)

### GIF tools by platform

#### Browser

- [GIPHY](https://giphy.com)
- [Chrome Capture](https://chrome.google.com/webstore/detail/chrome-capture/ggaabchcecdbomdcnbahdfddfikjmphe?hl=en)
  (Tip: Use Alt+i to interact with the page while recording)

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
