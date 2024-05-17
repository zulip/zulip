# Web frontend black-box Puppeteer tests

While our [node test suite](testing-with-node.md) is the
preferred way to test most frontend code because they are easy to
write and maintain, some code is best tested in a real browser, either
because of navigation (E.g. login) or because we want to verify the
interaction between Zulip logic and browser behavior (E.g. copy/paste,
keyboard shortcuts, etc.).

## Running tests

You can run this test suite as follows:

```bash
tools/test-js-with-puppeteer
```

See `tools/test-js-with-puppeteer --help` for useful options,
especially running specific subsets of the tests to save time when
debugging.

The test files live in `web/e2e-tests` and make use
of various useful helper functions defined in
`web/e2e-tests/lib/common.ts`.

## How Puppeteer tests work

The Puppeteer tests use a real Chromium browser (powered by
[puppeteer](https://github.com/puppeteer/puppeteer)), connected to a
real Zulip development server. These are black-box tests: Steps in a
Puppeteer test are largely things one might do as a user of the Zulip
web app, like "Type this key", "Wait until this HTML element
appears/disappears", or "Click on this HTML element".

For example, this function might test the `x` keyboard shortcut to
open the compose box for a new direct message:

```js
async function test_private_message_compose_shortcut(page) {
    await page.keyboard.press("KeyX");
    await page.waitForSelector("#private_message_recipient", {visible: true});
    await common.pm_recipient.expect(page, "");
    await close_compose_box(page);
}
```

The test function presses the `x` key, waits for the
`#private_message_recipient` input element to appear, verifies its
content is empty, and then closes the compose box. The
`waitForSelector` step here (and in most tests) is critical; tests
that don't wait properly often fail nonderministically, because the
test will work or not depending on whether the browser updates the UI
before or after executing the next step in the test.

Black-box tests are fantastic for ensuring the overall health of the
project, but are also slow, costly to maintain, and require care to
avoid nondeterministic failures, so we usually prefer to write a Node
test instead when both are options.

They also can be a bit tricky to understand for contributors not
familiar with [async/await][learn-async-await].

## Debugging Puppeteer tests

The following questions are useful when debugging Puppeteer test
failures you might see in [continuous
integration](continuous-integration.md):

- Does the flow being tested work properly in the Zulip browser UI?
  Test failures can reflect real bugs, and often it's easier and more
  interactive to debug an issue in the normal Zulip development
  environment than in the Puppeteer test suite.
- Does the change being tested adjust the HTML structure in a way that
  affects any of the selectors used in the tests? If so, the test may
  just need to be updated for your changes.
- Does the test fail deterministically when you run it locally using
  E.g. `./tools/test-js-with-puppeteer compose.ts`? If so, you can
  iteratively debug to see the failure.
- Does the test fail nondeterministically? If so, the problem is
  likely that a `waitForSelector` statement is either missing or not
  waiting for the right thing. Tests fail nondeterministically much
  more often on very slow systems like those used for Continuous
  Integration (CI) services because small races are amplified in those
  environments; this often explains failures in CI that cannot be
  easily reproduced locally.
- Does the test fail when you are typing (filling the form) on a modal
  or other just-opened UI widget? Puppeteer starts typing after focusing on
  the text field, sending keystrokes one after another. So, if
  application code explicitly focuses the modal after it
  appears/animates, this could cause the text field that Puppeteer is
  trying to type into to lose focus, resulting in partially typed data.
  The recommended fix for this is to wait until the modal is focused before
  starting typing, like this:
  ```JavaScript
  await page.waitForFunction(":focus").attr("id") === modal_id);
  ```

These tools/features are often useful when debugging:

- You can use `console.log` statements both in Puppeteer tests and the
  code being tested to print-debug.
- Zulip's Puppeteer tests are configured to generate screenshots of
  the state of the test browser when an assert statement fails; these
  are stored under `var/puppeteer/*.png` and are extremely helpful for
  debugging test failures.
- TODO: Mention how to access Puppeteer screenshots in CI.
- TODO: Add an option for using the `headless: false` debugging mode
  of Puppeteer so you can watch what's happening, and document how to
  make that work with Vagrant.
- TODO: Document `--interactive`.
- TODO: Document how to run 100x in CI to check for nondeterministic
  failures.
- TODO: Document any other techniques/ideas that were helpful when porting
  the Casper suite.
- The Zulip server powering these tests is just `run-dev` with some
  extra [Django settings](../subsystems/settings.md) from
  `zproject/test_extra_settings.py` to configure an isolated database
  so that the tests will not interfere/interact with a normal
  development environment. The console output while running the tests
  includes the console output for the server; any Python exceptions
  are likely actual bugs in the changes being tested.

See also [Puppeteer upstream's debugging
tips](https://github.com/puppeteer/puppeteer#debugging-tips); some
tips may require temporary patches to functions like `run_test` or
`ensure_browser` in `web/e2e-tests/lib/common.ts`.

## Writing Puppeteer tests

Probably the easiest way to learn how to write Puppeteer tests is to
study some of the existing test files. There are a few tips that can
be useful for writing Puppeteer tests in addition to the debugging
notes above:

- Run just the file containing your new tests as described above to
  have a fast debugging cycle.
- When you're done writing a test, run it 100 times in a loop to
  verify it does not fail nondeterministically (see above for notes on
  how to get CI to do it for you); this is important to avoid
  introducing extremely annoying nondeterministic failures into
  `main`.
- With black-box browser tests like these, it's very important to write your code
  to wait for browser's UI to update before taking any action that
  assumes the last step was processed by the browser (E.g. after you
  click on a user's avatar, you need an explicit wait for the profile
  popover to appear before you can try to click on a menu item in that
  popover). This means that before essentially every action in your
  Puppeteer tests, you'll want to use `waitForSelector` or similar
  wait function to make sure the page or element is ready before you
  interact with it. The [puppeteer docs site](https://pptr.dev/) is a
  useful reference for the available wait functions.
- When using `waitForSelector`, you always want to use the
  `{visible: true}` option; otherwise the test will stop waiting as
  soon as the target selector is present in the DOM even if it's
  hidden. For the common UI pattern of having an element always be
  present in the DOM whose presence is managed via show/hide rather
  than adding/removing it from the DOM, `waitForSelector` without
  `visible: true` won't wait at all.
- The test suite uses a smaller set of default user accounts and other
  data initialized in the database than the normal development
  environment; specifically, it uses the same setup as the [backend
  tests](testing-with-django.md). To see what differs from
  the development environment, check out the conditions on
  `options["test_suite"]` in
  `zilencer/management/commands/populate_db.py`.

[learn-async-await]: https://developer.mozilla.org/en-US/docs/Learn/JavaScript/Asynchronous/Async_await
