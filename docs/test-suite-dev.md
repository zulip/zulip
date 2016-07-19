# Running the test suite

Zulip tests must be run inside a Zulip development environment; if
you're using Vagrant, you will need to enter the Vagrant environment
before running the tests:

```
vagrant ssh
cd /srv/zulip
```

To run all the tests, do this:
```
./tools/test-all
```

For more details on how to run a single test, efficiently debug test
failures, or write tests, check out the [detailed testing
docs][tdocs].

[tdocs]: http://zulip.readthedocs.io/en/latest/testing.html



This runs the linter (`tools/lint-all`) plus all of our test suites;
they can all be run separately (just read `tools/test-all` to see
them).  You can also run individual tests which can save you a lot of
time debugging a test failure, e.g.:

```
./tools/lint-all # Runs all the linters in parallel
./tools/test-backend zerver.tests.test_bugdown.BugdownTest.test_inline_youtube
./tools/test-js-with-casper 09-navigation.js
./tools/test-js-with-node util.js
```

The above setup instructions include the first-time setup of test
databases, but you may need to rebuild the test database occasionally
if you're working on new database migrations.  To do this, run:

```
./tools/do-destroy-rebuild-test-database
```

## Possible testing issues

- When running the test suite, if you get an error like this:

  ```
      sqlalchemy.exc.ProgrammingError: (ProgrammingError) function ts_match_locs_array(unknown, text, tsquery) does not   exist
      LINE 2: ...ECT message_id, flags, subject, rendered_content, ts_match_l...
                                                                   ^
  ```

  … then you need to install tsearch-extras, described
  above. Afterwards, re-run the `init*-db` and the
  `do-destroy-rebuild*-database` scripts.

- When building the development environment using Vagrant and the LXC
  provider, if you encounter permissions errors, you may need to
  `chown -R 1000:$(whoami) /path/to/zulip` on the host before running
  `vagrant up` in order to ensure that the synced directory has the
  correct owner during provision. This issue will arise if you run `id
  username` on the host where `username` is the user running Vagrant
  and the output is anything but 1000.
  This seems to be caused by Vagrant behavior; for more information,
  see [the vagrant-lxc FAQ entry about shared folder permissions
  ][lxc-sf].

[lxc-sf]: https://github.com/fgrehm/vagrant-lxc/wiki/FAQ#help-my-shared-folders-have-the-wrong-owner)
