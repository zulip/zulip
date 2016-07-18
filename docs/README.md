# Documentation

These docs are written in [Commonmark
Markdown](http://commonmark.org/) with a small bit of rST.  We've
chosen Markdown because it is [easy to
write](http://commonmark.org/help).  The docs are served in production
at [zulip.readthedocs.io](https://zulip.readthedocs.io/en/latest/).

If you want to build the documentation locally (e.g. to test your
changes), the dependencies are automatically installed as part of
Zulip development environment provisioning, and you can build the
documentation using:

```
cd docs/
make html
```

and then opening `file:///path/to/zulip/docs/_build/html/index.html` in
your browser (you can also use e.g. `firefox
docs/_build/html/index.html` from the root of your Zulip checkout).

You can also usually test your changes by pushing a branch to GitHub
and looking at the content on the GitHub web UI, since GitHub renders
Markdown.

When editing dependencies for the Zulip documentation, you should edit
`requirements/docs.txt` (which is used by ReadTheDocs to build the
documentation quickly, without installing all of Zulip's dependencies).
