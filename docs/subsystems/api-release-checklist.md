# Zulip PyPI packages release checklist

Zulip manages the following three PyPI packages from the
[zulip/python-zulip-api][python-zulip-api] repository:

- [zulip][zulip-package]: The package containing the
  [Zulip API](https://zulip.com/api/) Python bindings.
- [zulip_bots][zulip-bots-package]: The package containing
  [Zulip's interactive bots](https://zulip.com/api/running-bots).
- [zulip_botserver][zulip-botserver-package]: The package for Zulip's Botserver.

The `python-zulip-api` packages are often released all together. Here is a
checklist of things one must do before making a PyPI release:

1. Increment `__version__` in `zulip/__init__.py`, `ZULIP_BOTS_VERSION` in
   `zulip_bots/setup.py`, and `ZULIP_BOTSERVER_VERSION` in
   `zulip_botserver/setup.py`. They should all be set to the same version
   number.

2. Set `IS_PYPA_PACKAGE` to `True` in `zulip_bots/setup.py`. **Note**:
   Setting this constant to `True` prevents `setup.py` from including content
   that should not be a part of the official PyPI release, such as logos,
   assets and documentation files. However, this content is required by the
   [Zulip server repo][zulip-repo] to render the interactive bots on
   [Zulip's integrations page](https://zulip.com/integrations/). The server
   repo installs the `zulip_bots` package
   directly from the GitHub repository so that this extra
   content is included in its installation of the package.

3. Follow PyPI's instructions in
   [Generating distribution archives][generating-dist-archives] to generate the
   archives for each package. It is recommended to manually inspect the build output
   for the `zulip_bots` package to make sure that the extra files mentioned above
   are not included in the archives.

4. Follow PyPI's instructions in [Uploading distribution archives][upload-dist-archives]
   to upload each package's archives to TestPyPI, which is a separate instance of the
   package index intended for testing and experimentation. **Note**: You need to
   [create a TestPyPI](https://test.pypi.org/account/register/) account for this step.

5. Follow PyPI's instructions in [Installing your newly uploaded package][install-pkg]
   to test installing all three packages from TestPyPI.

6. If everything goes well in step 5, you may repeat step 4, except this time, upload
   the packages to the actual Python Package Index.

7. Once the packages are uploaded successfully, set `IS_PYPA_PACKAGE` to `False` in
   `zulip_bots/setup.py` and commit your changes with the version increments. Push
   your commit to `python-zulip-api`. Create a release tag and push the tag as well.
   See [the tag][example-tag] and [the commit][example-commit] for the 0.8.1 release
   to see an example.

Now it is time to [update the dependencies](dependencies) in the
[Zulip server repository][zulip-repo]:

1. Increment `PROVISION_VERSION` in `version.py`. A minor version bump should suffice in
   most cases.

2. Update the release tags in the Git URLs for `zulip` and `zulip_bots` in
   `pyproject.toml`.

3. Run `uv lock` to update the Python lock file.

4. Commit your changes and submit a PR! **Note**: See
   [this example commit][example-zulip-commit] to get an idea of what the final change
   looks like.

## Other PyPI packages maintained by Zulip

Zulip also maintains two additional PyPI packages:

- [fakeldap][fakeldap]: A simple package for mocking LDAP backend servers
  for testing.
- [virtualenv-clone][virtualenvclone]: A package for cloning a non-relocatable
  virtualenv.

The release process for these two packages mirrors the release process for the
`python-zulip-api` packages, minus the steps specific to `zulip_bots` and the
update to dependencies required in the [Zulip server repo][zulip-repo].

[zulip-repo]: https://github.com/zulip/zulip
[python-zulip-api]: https://github.com/zulip/python-zulip-api
[zulip-package]: https://github.com/zulip/python-zulip-api/tree/main/zulip
[zulip-bots-package]: https://github.com/zulip/python-zulip-api/tree/main/zulip_bots
[zulip-botserver-package]: https://github.com/zulip/python-zulip-api/tree/main/zulip_botserver
[generating-dist-archives]: https://packaging.python.org/en/latest/tutorials/packaging-projects/#generating-distribution-archives
[upload-dist-archives]: https://packaging.python.org/en/latest/tutorials/packaging-projects/#uploading-the-distribution-archives
[install-pkg]: https://packaging.python.org/en/latest/tutorials/packaging-projects/#installing-your-newly-uploaded-package
[example-tag]: https://github.com/zulip/python-zulip-api/releases/tag/0.8.1
[example-commit]: https://github.com/zulip/python-zulip-api/commit/fec8cc50c42f04c678a0318f60a780d55e8f382b
[example-zulip-commit]: https://github.com/zulip/zulip/commit/0485aece4e58a093cf45163edabe55c6353a0b3a#
[fakeldap]: https://github.com/zulip/fakeldap
[virtualenvclone]: https://pypi.org/project/virtualenv-clone/
