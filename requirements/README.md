The dependency graph of the requirements is as follows:

```
dev +-> prod +-> common
+
|
v
docs,pip
```

Of the files, only dev and prod have been used in the install
scripts directly. The rest are implicit dependencies.

Steps to update a lock file, e.g. to update ipython from 5.3.0 to latest version:

0. Remove entry for `ipython==5.3.0` in dev.txt.
1. Run `./tools/update-locked-requirements`, which will generate new entries, pinned to the latest version.
2. Increase `PROVISION_VERSION` in `version.py`.
3. Run `./tools/provision` to install the new deps and test them.
4. Commit your changes.

## Testing custom modifications of a dependency

When working on Zulip, sometimes it is necessary to also make
modifications to a dependency (either to add a feature that we will
rely on, or to fix a bug that needs to be fixed for the intended
changes to work in Zulip) - with the idea that eventually they will be
merged upstream and included in an official release.

That process can take time however, and sometimes it'd be good to be
able to create and test your Zulip changes on top of changes to the
upstream package, without waiting for the potentially lengthy code
review and release process of the upstream dependency.

You can do this forking the upstream project, making the changes on a
branch in your fork, and then replacing the package's entry in
`dev.in` or `prod.in` with an appropriate GitHub link to the branch
with your modifications. The files have various examples of how this
should be done, but essentially you will add an entry looking like
this:

```
https://github.com/<your GitHub>/<package name>/archive/<commit hash>.zip#egg=<package name>==<version>+git
```

After that, you can follow the above process involving
`./tools/update-locked-requirements` and the following steps to have
the modified package installed in your dev environment, where it can
be used for testing.
