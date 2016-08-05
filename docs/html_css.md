# HTML and CSS

## Zulip CSS organization

The Zulip application's CSS can be found in the `static/styles/`
directory.  Zulip uses [Bootstrap](http://getbootstrap.com/) as its
main third-party CSS library.

Zulip currently does not use any CSS preprocessors, and is organized
into several files.  For most pages, the CSS is combined into a single
CSS file by the [static asset pipeline](front-end-build-process.html),
controlled by the `PIPELINE_CSS` code in `zproject/settings.py`.

The CSS files are:

* `portico.css` - Main CSS for logged-out pages
* `pygments.css` - CSS for Python syntax highlighting
* `activity.css` - CSS for the `activity` app
* `fonts.css` - Fonts for text in the Zulip app
* `static/styles/thirdparty-fonts.css` - Font Awesome (used for icons)

The CSS for the Zulip web application UI is primarily here:

* `settings.css` - CSS for the Zulip settings and administration pages
* `zulip.css` - CSS for the rest of the Zulip logged-in app
* `media.css` - CSS for media queries (particularly related to screen width)

We are in the process of [splitting zulip.css into several more
files](https://github.com/zulip/zulip/issues/731); help with that
project is very welcome!

## Editing Zulip CSS

If you aren't experienced with doing web development and want to make
CSS changes, we recommend reading the excellent [Chrome web inspector
guide on editing HTML/CSS](https://developer.chrome.com/devtools/docs/dom-and-styles),
especially the [section on
CSS](https://developer.chrome.com/devtools/docs/dom-and-styles#styles)
to learn about all the great tools that you can use to modify and test
changes to CSS interactively in-browser (without even having the
reload the page!).

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
