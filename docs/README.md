To create rST from MediaWiki input:

   * Use `pandoc -r mediawiki -w rst` on MediaWiki source.
   * Use unescape.py to remove any leftover HTML entities (often inside <pre>
     tags and the like).

We can use pandoc to translate mediawiki into reStructuredText, but some things need fixing up:

   * Add page titles.
   * Review pages for formatting (especially inline code chunks) and content.
   * Fix wiki links?
   * Add pages to the table of contents (`index.rst`).

To generate HTML docs locally from RST:

   * `pip install sphinx`
   * In this directory, `make html`. Output appears in a `_build/html` subdirectory.
