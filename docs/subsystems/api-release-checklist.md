# Zulip PyPI package release checklist

This document describes the steps to be followed when preparing
a new release of the
[PyPI package for our API bindings][1].

While performing the steps outlined below, we should adhere to
the guidelines presented in the
[Python Packaging User Guide](https://packaging.python.org/).

The steps below assume that you are familiar with the material
presented [here](https://packaging.python.org/tutorials/installing-packages/).

1. [Reconfigure the package][2], if need be (upgrade version
  number, development status, and so on).

2. Create a [source distribution][3].

3. Create a [pure Python Wheel][4].

4. [Upload][5] the distribution file(s) to [zulip-beta][6].

5. Post about the beta release in `#general` and test
   the [zulip-beta][6] package extensively.

6. Respond to the feedback received in **Step 5**.

7. Make final changes, upload the distribution file(s) to the
   main [zulip][1] package.

8. Post in `#general` about the new release.

**Note:** We may upload directly to the main [zulip][1] package
without beta-testing on [zulip-beta][6], if we feel that the changes
made in the new release are minor and not disruptive enough to
warrant extensive pretesting.

[1]: https://pypi.python.org/pypi/zulip/0.3.1
[2]: https://packaging.python.org/tutorials/distributing-packages/#configuring-your-project
[3]: https://packaging.python.org/tutorials/distributing-packages/#source-distributions
[4]: https://packaging.python.org/tutorials/distributing-packages/#pure-python-wheels
[5]: https://packaging.python.org/tutorials/distributing-packages/#upload-your-distributions
[6]: https://pypi.python.org/pypi/zulip-beta/0.2.5
