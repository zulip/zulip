# Documenting REST API endpoints

This document explains the system for documenting [Zulip's REST
API](https://zulip.com/api/rest).

Zulip's API documentation is an essential resource both for users and
for the developers of Zulip's mobile and terminal apps.  Our vision is
for the documentation to be sufficiently good that developers of
Zulip's apps should never need to look at the server's implementation
to answer questions about the API's semantics.

To achieve these goals, Zulip leverages the popular OpenAPI format as
the data source to ensure that Zulip's API documentation is correct
and remains so as Zulip's API evolves.

In particular, the top goal for this system is that all mistakes in
verifiable content (i.e. not the English explanations) should cause
the Zulip test suite to fail.  This is incredibly important, because
once you notice one error in API documentation, you no longer trust it
to be correct, which ends up wasting the time of its users.

Since it's very difficult to not make little mistakes when writing any
untested code, the only good solution to this is a way to test
the documentation.  We found dozens of errors in the process of adding
the validation Zulip has today.

Our API documentation is defined by a few sets of files:

* Most data describing API endpoints and examples is stored in our
  [OpenAPI configuration](../documentation/openapi.md) at
  `zerver/openapi/zulip.yaml`.
* The top-level templates live under `templates/zerver/api/*`, and are
  written using the Markdown framework that powers our [user
  docs](../documentation/user.md), with some special extensions for
  rendering nice code blocks and example responses.  We expect to
  eventually remove most of these files where it is possible to
  fully generate the documentation from the OpenAPI files.
* The text for the Python examples comes from a test suite for the
  Python API documentation (`zerver/openapi/python_examples.py`; run via
  `tools/test-api`).  The `generate_code_example` macro will magically
  read content from that test suite and render it as the code example.
  This structure ensures that Zulip's API documentation is robust to a
  wide range of possible typos and other bugs in the API
  documentation.
* The JavaScript examples are similarly generated and tested using
  `zerver/openapi/javascript_examples.js`.
* The cURL examples are generated and tested using
  `zerver/openapi/curl_param_value_generators.py`.
* The REST API index
  (`templates/zerver/help/include/rest-endpoints.md`) in the broader
  /api left sidebar (`templates/zerver/api/sidebar_index.md`).
* We have an extensive set of tests designed to validate that the data
  in this file is correct, `zerver/tests/test_openapi.py` compares
  every endpoint's accepted parameters in `views` code with those
  declared in `zulip.yaml`.  And [backend test
  suite](../testing/testing-with-django.md) and checks that every API
  response served during our extensive backend test suite matches one
  the declared OpenAPI schema for that endpoint.

This first section is focused on explaining how the API documentation
system is put together; when actually documenting an endpoint, you'll
want to also read the [Step by step guide](#step-by-step-guide).

1. [How it works](#how-it-works)
   1. [Description](#description)
   2. [Usage examples](#usage-examples)
   3. [Arguments](#parameters)
   4. [Responses](#displaying-example-payloads-or-responses)
2. [Step by step guide](#step-by-step-guide)
3. [Why a custom system](#why-a-custom-system)


## How it works

To understand how this documentation system works, start by reading an
existing doc file (`templates/zerver/api/render-message.md` is a good
example; accessible live
[here](https://zulip.com/api/render-message) or in the development
environment at `http://localhost:9991/api/render-message`).

We highly recommend looking at those resources while reading this page.

If you look at the documentation for existing endpoints, you'll notice
that a typical endpoint's documentation is divided into four sections:

* The top-level [**Description**](#description)
* [**Usage examples**](#usage-examples)
* [**Arguments**](#parameters)
* [**Responses**](#displaying-example-payloads-or-responses)

The rest of this guide describes how each of these sections works.

### Description

Displayed at the top of any REST endpoint documentation page, this
should explain what the endpoint does in clear English. Include
details on how to use it correctly or what it's good or bad for, with
links to any alternative endpoints the user might want to consider.

These sections should often contain a link to the documentation of the
relevant feature in `/help/`.

### Usage examples

We display usage examples in three languages: Python, JavaScript and
`curl`; we may add more in the future.  Every endpoint should have
Python and `curl` documentation; `JavaScript` is optional as we don't
consider that API library to be fully supported.  The examples are
defined using a special Markdown extension
(`zerver/openapi/markdown_extension.py`).  To use this extension, one
writes a Markdown file block that looks something like this:

```
{start_tabs}
{tab|python}

{generate_code_example(python)|/messages/render:post|example}

{tab|js}
...

{tab|curl}

{generate_code_example(curl)|/messages/render:post|example}

{end_tabs}
```

#### Writing Python examples

For the Python examples, you'll write the example in
`zerver/openapi/python_examples.py`, and it'll be run and verified
automatically in Zulip's automated test suite.  The code there will
look something like this:

``` python
@openapi_test_function('/messages/render:post')
def render_message(client: Client) -> None:
    # {code_example|start}
    # Render a message
    request = {
        'content': '**foo**'
    }
    result = client.render_message(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages/render', 'post', '200')
```

This is an actual Python function which will be run as part of the
`tools/test-api` test suite.  The `validate_against_opanapi_schema`
function will verify that the result of that request is as defined in
the examples in `zerver/openapi/zulip.yaml`.

To run as part of the testsuite, the `render_message` function needs
to be called from `test_messages` (or one of the other functions at
the bottom of the file).  The final function, `test_the_api`, is what
actually runs the tests.  Tests with the `openapi_test_function`
decorator that are not called will fail tests, as will new endpoints
that are not covered by an `openapi_test_function`-decorated test.

You will still want to manually test the example using Zulip's Python
API client by copy-pasting from the website; it's easy to make typos
and other mistakes where variables are defined outside the tested
block, and the tests are not foolproof.

The code that renders `/api` pages will extract the block between the
`# {code_example|start}` and `# {code_example|end}` comments, and
substitute it in place of
`{generate_code_example(python)|/messages/render:post|example}`
wherever that string appears in the API documentation.

### Parameters

We have a separate Markdown extension to document the parameters that
an API endpoint supports.  You'll see this in files like
`templates/zerver/api/render-message.md` via the following Markdown
directive (implemented in
`zerver/lib/markdown/api_arguments_table_generator.py`):

```
{generate_api_arguments_table|zulip.yaml|/messages/render:post}
```

Just as in the usage examples, the `/messages/render` key must match a
URL definition in `zerver/openapi/zulip.yaml`, and that URL definition
must have a `post` HTTP method defined.

### Displaying example payloads or responses

If you've already followed the steps in the [Usage examples](#usage-examples)
section, this part should be fairly trivial.

You can use the following Markdown directive to render all the fixtures
defined in the OpenAPI `zulip.yaml` for a given endpoint

```
{generate_code_example|/messages/render:post|fixture}
```

## Step by step guide

This section offers a step-by-step process for adding documentation
for a new API endpoint.  It assumes you've read and understood the
above.

1. Start by adding [OpenAPI format](../documentation/openapi.md)
   data to `zerver/openapi/zulip.yaml` for the endpoint.  If you
   copy-paste (which is helpful to get the indentation structure
   right), be sure to update all the content that you copied to
   correctly describe your endpoint!

   In order to do this, you need to figure out how the endpoint in
   question works by reading the code!  To understand how arguments
   are specified in Zulip backend endpoints, read our [REST API
   tutorial][rest-api-tutorial], paying special attention to the
   details of `REQ` and `has_request_variables`.

   Once you understand that, the best way to determine the supported
   arguments for an API endpoint is to find the corresponding URL
   pattern in `zprojects/urls.py`, look up the backend function for
   that endpoint in `zerver/views/`, and inspect its arguments
   declared using `REQ`.

   You can check your formatting using these helpful tools.
   * `tools/check-openapi` will verify the syntax of `zerver/openapi/zulip.yaml`.
   * `tools/test-backend zerver/tests/test_openapi.py`; this test compares
      your documentation against the code and can find many common
      mistakes in how arguments are declared.
   * `test-backend`: The full Zulip backend test suite will fail if
     any actual API responses generated by the tests don't match your
     defined OpenAPI schema.  Use `test-backend --rerun` for a fast
     edit/refresh cycle when debugging.

   [rest-api-tutorial]: ../tutorials/writing-views.html#writing-api-rest-endpoints

1. Add a function for the endpoint you'd like to document to
   `zerver/openapi/python_examples.py`, decorated with
   `@openapi_test_function`. `render_message` is a good example to
   follow.  There are generally two key pieces to your test: (1) doing
   an API query and (2) verifying its result has the expected format
   using `validate_against_openapi_schema`.

1. Make the desired API call inside the function. If our Python
   bindings don't have a dedicated method for a specific API call,
   you may either use `client.call_endpoint` or add a dedicated
   function to the [zulip PyPI
   package](https://github.com/zulip/python-zulip-api/tree/master/zulip).
   Ultimately, the goal is for every endpoint to be documented the
   latter way, but it's useful to be able to write working
   documentation for an endpoint that isn't supported by
   `python-zulip-api` yet.

1. Add the function to one of the `test_*` functions at the end of
   `zerver/openapi/python_examples.py`; this will ensure your
   function will be called when running `test-api`.

1. Capture the JSON response returned by the API call (the test
   "fixture").  The easiest way to do this is add an appropriate print
   statement (usually `json.dumps(result, indent=4, sort_keys=True)`),
   and then run `tools/test-api`.  You can also use
   <https://jsonformatter.curiousconcept.com/> to format the JSON
   fixtures.  Add the fixture to the `example` subsection of the
   `responses` section for the endpoint in
   `zerver/openapi/zulip.yaml`.

1. Run `./tools/test-api` to make sure your new test function is being
   run and the tests pass.

1. Now, inside the function, isolate the lines of code that call the API and could
   be displayed as a code example. Wrap the relevant lines in
   `# {code_example|start} ... relevant lines go here ... # {code_example|end}`
   comments. The lines inside these comments are what will be displayed as the
   code example on our `/api` page.

1. Finally, write the Markdown file for your API endpoint under
   `templates/zerver/api/`.  This is usually pretty easy to template
   off existing endpoints; but refer to the system explanations above
   for details.

1. Add the Markdown file to the index in `templates/zerver/help/include/rest-endpoints.md`.

1. Test your endpoint, pretending to be a new user in a hurry, by
   visiting it via the links on `http://localhost:9991/api` (the API
   docs are rendered from the Markdown source files on page load, so
   just reload to see an updated version as you edit).  You should
   make sure that copy-pasting the code in your examples works, and
   post an example of the output in the pull request.

1. Document the new API in `templates/zerver/api/changelog.md` and
   bump the `API_FEATURE_LEVEL` in `version.py`. Also, make sure to
   add a `**Changes**` entry in the description of the new API/event
   in `zerver/openapi/zulip.yaml`, which mentions the API feature level
   at which they were added.

[javascript-examples]: https://github.com/zulip/zulip-js/tree/master/examples

## Why a custom system?

Given that our documentation is written in large part using the
OpenAPI format, why maintain a custom Markdown system for displaying
it?  There's several major benefits to this system:

* It is extremely common for API documentation to become out of date
  as an API evolves; this automated testing system helps make it
  possible for Zulip to maintain accurate documentation without a lot
  of manual management.
* Every Zulip server can host correct API documentation for its
  version, with the key variables (like the Zulip server URL) already
  pre-substituted for the user.
* We're able to share implementation language and visual styling with
  our Help Center, which is especially useful for the extensive
  non-REST API documentation pages (e.g. our bot framework).

Using the standard OpenAPI format gives us flexibility, though; if we
later choose to migrate to third-party tools, we don't need to redo
the actual documentation work in order to migrate tools.
