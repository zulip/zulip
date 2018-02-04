# Accessibility

## Guidelines

In order to accommodate all users, Zulip strives to implement accessibility
best practices in its user interface.  There are many aspects to accessibility;
here are some of the more important ones to keep in mind.

* All images should have alternative text attributes for the benefit of users
  who cannot see them (this includes users who are utilizing a voice interface
  to free up their eyes to look at something else instead).
* The entire application should be usable via a keyboard (many users are unable
  to use a mouse, and many accessibility aids emulate a keyboard).
* Text should have good enough contrast against the background to enable
  even users with moderate visual impairment to be able to read it.
* [ARIA](https://www.w3.org/WAI/intro/aria) (Accessible Rich Internet
  Application) attributes should be used appropriately to enable screen
  readers and other alternative interfaces to navigate the application
  effectively.

There are many different standards for accessibility, but the most relevant
one for Zulip is the W3C's [WCAG](https://www.w3.org/TR/WCAG20/) (Web Content
Accessibility Guidelines), currently at version 2.0.  Whenever practical, we
should strive for compliance with the AA level of this specification.
(The W3C itself
[recommends not trying](https://www.w3.org/TR/UNDERSTANDING-WCAG20/conformance.html#uc-conf-req1-head)
to comply with the highest AAA level for an entire web site or application,
as it is not possible for some content.)

## Tools

There are tools available to automatically audit a web page for compliance
with many of the WCAG guidelines.  Here are some of the more useful ones:

* [Accessibility Developer Tools][chrome-webstore]
  This open source Chrome extension from Google adds an accessibility audit to
  the "Audits" tab of the Chrome Developer Tools.  The audit is performed
  against the page's DOM via JavaScript, allowing it to identify some issues
  that a static HTML inspector would miss.
* [aXe](https://www.deque.com/products/axe/) An open source Chrome and Firefox
  extension which runs a somewhat different set of checks than Google's Chrome
  extension.
* [Wave](http://wave.webaim.org/) This web application takes a URL and loads
  it in a frame, reporting on all the issues it finds with links to more
  information.  Has the advantage of not requiring installation, but requires
  a URL which can be directly accessed by an external site.
* [Web Developer](http://chrispederick.com/work/web-developer/) This browser
  extension has many useful features, including a convenient link for opening
  the current URL in Wave to get an accessibility report.

Note that these tools cannot catch all possible accessibility problems, and
sometimes report false positives as well.  They are a useful aid in quickly
identifying potential problems and checking for regressions, but their
recommendations should not be blindly obeyed.

## GitHub Issues

Problems with Zulip's accessibility should be reported as
[GitHub issues](https://github.com/zulip/zulip/issues) with the "accessibility"
label.  This label can be added by entering the following text in a separate
comment on the issue:

    @zulipbot label "accessibility"

If you want to help make Zulip more accessible, here is a list of the
[currently open accessibility issues][accessibility-issues].

## Additional Resources

For more information about making Zulip accessible to as many users as
possible, the following resources may be useful.

* [Font Awesome accessibility guide](http://fontawesome.io/accessibility/),
  which is especially helpful since Zulip uses Font Awesome for its icons.
* [Web Content Accessibility Guidelines (WCAG) 2.0](https://www.w3.org/TR/WCAG/)
* [WAI-ARIA](https://www.w3.org/WAI/intro/aria) - Web Accessibility Initiative
  Accessible Rich Internet Application Suite
* [WebAIM](http://webaim.org/) - Web Accessibility in Mind
* The [MDN page on accessibility](https://developer.mozilla.org/en-US/docs/Web/Accessibility)
* The [Open edX Accessibility Guidelines][openedx-guidelines] for developers


[chrome-webstore]: https://chrome.google.com/webstore/detail/accessibility-developer-t/fpkknkljclfencbdbgkenhalefipecmb
[openedx-guidelines]: http://edx.readthedocs.io/projects/edx-developer-guide/en/latest/conventions/accessibility.html
[accessibility-issues]: https://github.com/zulip/zulip/issues?q=is%3Aissue+is%3Aopen+label%3A%22area%3A%20accessibility%22
