# Contribution Guide

*Note: this guide has been heavily inspired by [PhantomJS' one](https://github.com/ariya/phantomjs/blob/master/CONTRIBUTING.md).*

**This page describes how to contribute changes to the [CasperJS](http://casperjs.org/) project.**

Please do **not** create a pull request without reading this guide first. Failure to do so may result in the **rejection** of the pull request.

## For The Impatients

**Work on a feature branch**.
If your changes need to be modified due to some reviews, it is less clutter to tweak an isolated feature branch and push it again.

**Create a ticket in the [issue tracker](https://github.com/n1k0/casperjs/issues/)**.
This serves as a placeholder for important feedback, review, or any future updates. **Please ensure searching the bugtracker for an already opened issue matching your case before filing a new issue.**

In the commit message(s):

* **Keep the first line short**. Write additional paragraphs if necessary.
* **Reference an opened issue**, by referencing the issue ID prefixed by a `#` and the keyword `refs`, eg. `refs #123`

Sample commit message:

> refs #123 - fixed error message formatting
>
> (optional: a short explanation of what the patch actually does)

**Run tests**

Run CasperJS' test suite to see you didn't break something:

    $ casperjs selftest

The result status bar **must be green** before sending your PR.

## Communicate

**Improvement and feature request**. If you have an improvement idea, please send an email to the [mailing list](http://groups.google.com/group/casperjs) (preferable than contacting the developers directly) so that other people can give their insights and opinions. This is also important to avoid duplicate work.

**Help request**. If you're stuck using CasperJS and don't understand how to achieve something, please [ask on the mailing-list](https://groups.google.com/forum/#!forum/casperjs) first. Please don't ask for all the kind people to write your scripts for you.

**Ensure the issue is related to CasperJS**. Please try to reproduce the issue using plain PhantomJS. If it works with the native PhantomJS API but doesn't with CasperJS, then the issue is probably valid. In the opposite case, please file an issue on [PhantomJS issue tracker](http://code.google.com/p/phantomjs/issues/list).

**Extending with new API**. Whenever you want to introduce a new API, please send an email to the mailing list along with the link to the issue if any. It may require few iterations to agree on the final API and hence it is important to engage all interested parties as early as possible.

## Get Ready

### Use Feature Branch

To isolate your change, please avoid working on the master branch. Instead, work on a *feature branch* (often also known as *topic branch*). You can create a new branch (example here crash-fix) off the master branch by using:

    git checkout -b crash-fix master

Refer to your favorite Git tutorial/book for further detailed help.

Some good practices for the feature branch:

* Give it a meaningful name instead of, e.g. `prevent-zero-divide` instead of just `fix`
* Make *granular* and *atomic* commits, e.g. do not mix a typo fix with some major refactoring
* Keep one branch for one specific issue. If you need to work on other unrelated issues, create another branch.

### Write tests

CasperJS being partly a testing framework, how irrelevant would be to send a pull request with no test? So, please take the time to write and attach tests to your PR. Furthermore, testing with CasperJS is quite [exhaustively documented](http://casperjs.org/testing.html).

### Run tests!

This may sound obvious but **don't send pull requests which break the casperjs test suite**.

To see if your modifications broke the suite, just run:

    $ casperjs selftest

### Write documentation

Do you appreciate the [CasperJS documentation](http://casperjs.org/)? I do too. As the documentation contents are managed and generated using Github, Markdown and CasperJS itself, take the time to read the [Documentation Contribution Guide](https://github.com/n1k0/casperjs/blob/gh-pages/README.md#casperjs-documentation) and write the documentation related to your PR whenever applicable.

**Note:** As the documentation is handled in a [dedicated separated `gh-pages` branch](https://github.com/n1k0/casperjs/tree/gh-pages), you'll have to send a dedicated PR for doc patches. I'm working on a more comfortable solution, but it's no easy task though.

## Review and Merge

When your branch is ready, send the pull request.

While it is not always the case, often it is necessary to improve parts of your code in the branch. This is the actual review process.

Here is a check list for the review:

* It does not break the test suite
* There is no typo
* The coding style follows the existing one
* There is a reasonable amount of comment
* The license header is intact
* All examples are still working
