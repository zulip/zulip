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

You can also usually test your changes by pushing a branch to GitHub
and looking at the content on the GitHub web UI, since GitHub renders
Markdown.

When editing the dependencies for the Zulip documentation, you'll want
to edit both the root requirements.txt as well as
`docs/requirements.readthedocs.txt` (which is used by ReadTheDocs to
build the documentation quickly, without installing all of Zulip's
dependencies).
