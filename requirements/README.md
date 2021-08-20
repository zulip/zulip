The dependency graph of the requirements is as follows:

```
dev +-> prod +-> common
+
|
v
mypy,docs,pip
```

Of the files, only dev, prod, and mypy have been used in the install
scripts directly. The rest are implicit dependencies.

Steps to update a lock file, e.g. to update ipython from 5.3.0 to latest version:

0. Remove entry for `ipython==5.3.0` in dev.txt.
1. Run `./tools/update-locked-requirements`, which will generate new entries, pinned to the latest version.
2. Increase `PROVISION_VERSION` in `version.py`.
3. Run `./tools/provision` to install the new deps and test them.
4. Commit your changes.
