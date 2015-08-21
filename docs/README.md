These docs are written in rST, and are included on the zulip.org website
as well as on each development installation.  Many of these docs
have been ported from the internal docs of Zulip Inc.,
and may need to be updated for use in the open source project.

To generate HTML docs locally from rST:

   * `pip install sphinx`
   * In this directory, `make html`. Output appears in a `_build/html` subdirectory.

To create rST from MediaWiki input:

   * Use `pandoc -r mediawiki -w rst` on MediaWiki source.
   * Use unescape.py to remove any leftover HTML entities (often inside <pre>
     tags and the like).

We can use pandoc to translate mediawiki into reStructuredText, but some things need fixing up:

   * Add page titles.
   * Review pages for formatting (especially inline code chunks) and content.
   * Fix wiki links?
   * Add pages to the table of contents (`index.rst`).

