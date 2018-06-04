# Documenting REST API endpoints

This document briefly explains how to document
[Zulip's REST API endpoints](https://zulipchat.com/api/rest).

Our API documentation files live under `templates/zerver/api/*`. To begin,
we recommend copying over an existing doc file (`render-message.md` is a good
example) and using it as a template. Make sure you link to your new Markdown
file in `templates/zerver/help/rest-endpoints.md`, so that it can be displayed
in the sidebar on the `/api` page.

If you look at the documentation for existing endpoints (see a live example
[here](https://zulipchat.com/api/render-message)), you'll notice that the
documentation is roughly divided into three sections: **Usage examples**,
**Arguments**, and **Response**. The rest of this guide describes how to write
each of these sections.

## Usage examples

We display usage examples in three languages: Python, JavaScript and `curl`.
For JavaScript and `curl` we simply recommend copying and pasting the examples
directly into the Markdown file. JavaScript examples should conform to the
coding style and structure of [Zulip's existing JavaScript examples][1].
However, since Zulip's Python bindings are used most frequently, the process
of adding Python examples for an endpoint is a bit more involved.

[1]: https://github.com/zulip/zulip-js/tree/master/examples

We recommend skimming `zerver/lib/api_test_helpers.py` before proceeding with the
steps below.

1. Add a function for the endpoint you'd like to document to
   `zerver/lib/api_test_helpers.py`. `render_message` is a good example to
   follow.

1. Add the function to the `TEST_FUNCTIONS` dict.

1. Make the desired API call inside the function. If our Python bindings don't
   have a dedicated method for a specific API call, you may either use
   `client.call_endpoint` or add a dedicated function to the
   [zulip PyPI package](https://github.com/zulip/python-zulip-api/tree/master/zulip).

1. Capture the fixture returned by the API call and add it to
   `templates/zerver/api/fixtures.json`, where the key is the name of the Markdown
   file documenting the endpoint (without the `.md` extension), and the value is
   the fixture JSON object. Make sure that the JSON is formatted properly before
   you add it to `fixtures.json` (see [Formatting JSON](#formatting-json) for more
   info).

1. In `zerver/lib/api_test_helpers.py`, use `test_against_fixture` to test the
   result of the API call against the fixture captured in the previous step. This
   should be done inside the function you added in step 1. Make sure you update the
   `test_*` functions at the end of `zerver/lib/api_test_helpers.py` apppropriately.

1. Run `./tools/test-api` to make sure the tests pass.

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

This Markdown-based framework allows us to extract code examples from within tests,
which makes sure that code examples never get out of date or fail, and if they do,
`./tools/test-api` complains very loudly. To learn more about how this Markdown
extension works, see `zerver/lib/bugdown/api_code_examples.py`.

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
