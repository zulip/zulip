# Documenting REST API endpoints

This document briefly explains how to document
[Zulip's REST API endpoints](https://zulipchat.com/api/rest).

Our API documentation files live under `templates/zerver/api/*`. To
begin, we recommend using an existing doc file (`render-message.md` is
a good example) as a template. Make sure you link to your new Markdown
file in `templates/zerver/help/include/rest-endpoints.md` , so that it appears
in the index in the left sidebar on the `/api` page.

The markdown framework is the same one used by the
[user docs](../subsystems/user-docs.html), which supports macros and
various other features, though we don't use them heavily here.

If you look at the documentation for existing endpoints (see a live
example [here](https://zulipchat.com/api/render-message)), you'll
notice that a typical endpoint's documentation is roughly divided into
three sections: **Usage examples**, **Arguments**, and
**Response**. The rest of this guide describes how to write each of
these sections.

There's also a small section at the top, where you'll want to explain
what the endpoint does in clear English, and any important notes on
how to use it correctly or what it's good or bad for.

## Usage examples

We display usage examples in three languages: Python, JavaScript and `curl`.
For JavaScript and `curl` we simply recommend copying and pasting the examples
directly into the Markdown file. JavaScript examples should conform to the
coding style and structure of [Zulip's existing JavaScript examples][1].
However, since Zulip's Python bindings are used most frequently, the process
of adding Python examples for an endpoint have a more involved process
that includes automated tests for your documentation(!).

[1]: https://github.com/zulip/zulip-js/tree/master/examples

We recommend skimming `zerver/lib/api_test_helpers.py` before proceeding with the
steps below.

1. Start adding a function for the endpoint you'd like to document to
   `zerver/lib/api_test_helpers.py`. `render_message` is a good
   example to follow.  There are generally two key pieces to your
   test: (1) doing an API query and (2) verifying its result is
   as expected using `test_against_fixture`.

1. Make the desired API call inside the function. If our Python bindings don't
   have a dedicated method for a specific API call, you may either use
   `client.call_endpoint` or add a dedicated function to the
   [zulip PyPI package](https://github.com/zulip/python-zulip-api/tree/master/zulip).
   Ultimately, the goal is for every endpoint to be documented the
   latter way, but it's nice to be able to write your docs before you
   have to finish writing dedicated functions.

1. Add the function to the `TEST_FUNCTIONS` dict and one of the
   `test_*` functions at the end of `zerver/lib/api_test_helpers.py`;
   these will ensure your function will be called when running `test-api`.

1. Capture the JSON response returned by the API call (the test
   "fixture").  The easiest way to do this is add an appropriate print
   statement, and then run `tools/test-api` (see
   [Formatting JSON](#formatting-json) for how to get in it the right
   JSON format).  Add the fixture to
   `templates/zerver/api/fixtures.json`, where the key is the name of
   the Markdown file documenting the endpoint (without the `.md`
   extension), and the value is the fixture JSON object.

1. Run `./tools/test-api` to make sure your new test function is being
   run and the tests pass.

1. Now, inside the function, isolate the lines of code that call the API and could
   be displayed as a code example. Wrap the relevant lines in
   `# {code_example|start} ... relevant lines go here ... # {code_example|end}`
   comments. The lines inside these comments are what will be displayed as the
   code example on our `/api` page.

1. You may now use the following Markdown directive to render the lines inside the
   `# {code_example|start}` and `# {code_example|end}` blocks in your Markdown file,
   like so:

    ```
    {generate_code_example(python)|KEY_IN_TEST_FUNCTIONS|example}
    ```

    `KEY_IN_TEST_FUNCTIONS` is the key in the `TEST_FUNCTIONS` dict (added in step 2)
    that points to your test function.

This Markdown-based framework allows us to extract code examples from
within tests, which makes sure that code examples never get out of
date, since if they do, `./tools/test-api` will fail in our continuous
integration. To learn more about how this Markdown extension works,
see `zerver/lib/bugdown/api_code_examples.py`.

## Documenting arguments

We have a separate Markdown extension to document the arguments that
an API endpoint expects.

Essentially, you document the arguments for a specific endpoint in
`templates/zerver/api/arguments.json`, where the key is the name of the
Markdown file documenting the endpoint, and the value is the JSON object
describing the arguments.

You can use the following Markdown directive to render the arguments'
documentation as a neatly organized table:

```
{generate_api_arguments_table|arguments.json|KEY_IN_ARGUMENTS_FILE}
```

`KEY_IN_ARGUMENTS_FILE` refers to the key in `arguments.json`, usually
the name of the Markdown file where it will be used. To learn more about
how this Markdown extension works, see
`zerver/lib/bugdown/api_arguments_table_generator.py`.

The best way to find out what arguments an API endpoint takes is to
find the corresponding URL pattern in `zprojects/urls.py` and examining
the backend function that the URL pattern points to.

Be careful here!  There's no currently automated testing verifying
that the arguments match the code.

## Displaying example payloads/responses

If you've already followed the steps in the [Usage examples](#usage-examples)
section, this part should be fairly trivial.

You can use the following Markdown directive to render the fixtures stored
in `templates/zerver/api/fixtures.json`:

```
{generate_code_example|KEY_IN_FIXTURES_FILE|fixture}
```

`KEY_IN_FIXTURES_FILE` refers to the key in `fixtures.json`, which is
usually the name of the Markdown file (without the `.md` extension) where
it will be used. You may add more fixtures to `fixtures.json`, if necessary.
To learn more about how this Markdown extension works, see
`zerver/lib/bugdown/api_code_examples.py`.

## Formatting JSON

A quick way to format JSON is to use the Python `json` module and use the command
`json.dumps(json_dict, indent=4, sort_keys=True)`, where `json_dict` is the JSON
object (which is a Python dict) to be formatted.

You can also use <http://jsonformatter.curiousconcept.com/> to format the JSON
fixtures.
