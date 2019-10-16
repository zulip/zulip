# HTML and CSS

## Zulip CSS organization

The Zulip application's CSS can be found in the `static/styles/`
directory.  Zulip uses [Bootstrap](http://getbootstrap.com/) as its
main third-party CSS library.

Zulip uses SCSS for its CSS files.  There are two high-level sections
of CSS: the "portico" (logged-out pages like /help/, /login/, etc.),
and the app.  The portico CSS lives under the `static/styles/portico`
subdirectory.

## Editing Zulip CSS

If you aren't experienced with doing web development and want to make
CSS changes, we recommend reading the excellent [Chrome web inspector
guide on editing HTML/CSS](https://developer.chrome.com/devtools/docs/dom-and-styles),
especially the [section on
CSS](https://developer.chrome.com/devtools/docs/dom-and-styles#styles)
to learn about all the great tools that you can use to modify and test
changes to CSS interactively in-browser (without even having the
reload the page!).

Zulip's development environment has hot code reloading configured, so
changes made in source files will immediately take effect in open
browser windows, either by live-updating the CSS or reloading the
browser window (following backend changes).

## CSS Style guidelines

### Avoid duplicated code

Without care, it's easy for a web application to end up with thousands
of lines of duplicated CSS code, which can make it very difficult to
understand the current styling or modify it.  We would very much like
to avoid such a fate.  So please make an effort to reuse existing
styling, clean up now-unused CSS, etc., to keep things maintainable.

### Be consistent with existing similar UI

Ideally, do this by reusing existing CSS declarations, so that any
improvements we make to the styling can improve all similar UI
elements.

### Use clear, unique names for classes and object IDs

This makes it much easier to read the code and use `git grep` to find
where a particular class is used.

## Validating CSS

When changing any part of the Zulip CSS, it's important to check that
the new CSS looks good at a wide range of screen widths, from very
wide screen (e.g. 1920px) all the way down to narrow phone screens
(e.g. 480px).

For complex changes, it's definitely worth testing in a few different
browsers to make sure things look the same.
