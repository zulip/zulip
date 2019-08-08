# Documenting REST API endpoints

This document explains the system for documenting [Zulip's REST
API](https://zulipchat.com/api/rest).  This documentation is an
essential resource both for users and the developers of Zulip's mobile
and terminal apps. We carefully designed a system for both displaying
it and helping ensure it stays up to date as Zulip's API changes.

Our API documentation is defined by a few sets of files:

* Most data describing API endpoints and examples is stored in our
  [OpenAPI configuration](../documentation/openapi.html) at
  `zerver/openapi/zulip.yaml`.
* The top-level templates live under `templates/zerver/api/*`, and are
  written using the markdown framework that powers our [user
  docs](../documentation/user.html), with some special extensions for
  rendering nice code blocks and example responses.
* The text for the Python examples comes from a test suite for the
  Python API documentation (`zerver/openapi/python_examples.py`; run via
  `tools/test-api`).  The `generate_code_example` macro will magically
  read content from that test suite and render it as the code example.
  This structure ensures that Zulip's API documentation is robust to a
  wide range of possible typos and other bugs in the API
  documentation.
* The REST API index
  (`templates/zerver/help/include/rest-endpoints.md`) in the broader
  /api left sidebar (`templates/zerver/api/sidebar_index.md`).

This first section is focused on explaining how the API documentation
system is put together; when actually documenting an endpoint, you'll
want to also read the [Step by step guide][#step-by-step-guide].

## How it works

To understand how this documentation system works, start by reading an
existing doc file (`templates/zerver/api/render-message.md` is a good
example; accessible live
[here](https://zulipchat.com/api/render-message) or in the development
environment at `http://localhost:9991/api/render-message`).

We highly recommend looking at those resouces while reading this page.

If you look at the documentation for existing endpoints, you'll notice
that a typical endpoint's documentation is divided into four sections:

* The top-level **Description**
* **Usage examples**
* **Arguments**
* **Responses**

The rest of this guide describes how each of these sections works.

### Description

At the top of any REST endpoint documentation page, you'll want to
explain what the endpoint does in clear English. Including important
notes on how to use it correctly or what it's good or bad for, with
links to any alternative endpoints the user might want to consider.
These sections should almost always contain a link to the
documentation of the relevant feature in `/help/`.

We plan to migrate to storing this description content in the
`description` field in `zulip.yaml`; currently, the `description`
section in `zulip.yaml` is not used for anything.

### Usage examples

We display usage examples in three languages: Python, JavaScript and
`curl`; we may add more in the future.  Every endpoint should have
Python and `curl` documentation; `JavaScript` is optional as we don't
consider that API library to be fully supported.  The examples are
defined using a special Markdown extension
(`zerver/lib/bugdown/api_code_examples.py`).  To use this extension,
one writes a Markdown file block that looks something like this:

```
{start_tabs}
{tab|python}
{generate_code_example(python)|/messages/render:post|example}
{tab|curl}
curl -X POST {{ api_url }}/v1/messages/render \
...
{tab|javascript}
...
{end_tabs}
```

For JavaScript and `curl` examples, we just have the example right
there in the markdown file.  It is **critical** that these examples be
tested manually by copy-pasting the result; it is very easy and very
embarrassing to have typos result in incorrect documentation.
Additionally, JavaScript examples should conform to the coding style
and structure of [Zulip's existing JavaScript examples][javascript-examples].

For the Python examples, you'll write the example in
`zerver/openapi/python_examples.py`, and it'll be run and verified
automatically in Zulip's automated test suite.  The code there will
look something like this:

``` python
def render_message(client):
    # type: (Client) -> None

    # {code_example|start}
    # Render a message
    request = {
        'content': '**foo**'
    }
    result = client.render_message(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages/render', 'post', '200')
```

This is an actual Python function which (if registered correctly) will
be run as part of the `tools/test-api` test suite.  The
`validate_against_opanapi_schema` function will verify that the result
of that request is as defined in the examples in
`zerver/openapi/zulip.yaml`.  To register a function correctly:

* You need to add it to the `TEST_FUNCTIONS` map; this declares the
  relationship between function names like `render_message` and
  OpenAPI endpoints like `/messages/render:post`.
* The `render_message` function needs to be called from
  `test_messages` (or one of the other functions at the bottom of the
  file).  The final function, `test_the_api`, is what actually runs
  the tests.
* Test that your code actually runs in `tools/test-api`; a good way to
  do this is to break your code and make sure `tools/test-api` fails.

You will still want to manually test the example using Zulip's Python
API client by copy-pasting from the website; it's easy to make typos
and other mistakes where variables are defined outside the tested
block, and the tests are not foolproof.

The code that renders `/api` pages will extract the block between the
`# {code_example|start}` and `# {code_example|end}` comments, and
substitute it in place of
`{generate_code_example(python)|/messages/render:post|example}`
wherever that string appears in the API documentation.

### Arguments

We have a separate Markdown extension to document the arguments that
an API endpoint expects.  You'll see this in files like
`templates/zerver/api/render-message.md` via the following Markdown
directive (implemented in
`zerver/lib/bugdown/api_arguments_table_generator.py`):

```
{generate_api_arguments_table|zulip.yaml|/messages/render:post}
```

Just as in the usage examples, the `/messages/render` key must match a
URL definition in `zerver/openapi/zulip.yaml`, and that URL definition
must have a `post` HTTP method defined.

### Displaying example payloads/responses

If you've already followed the steps in the [Usage examples](#usage-examples)
section, this part should be fairly trivial.

You can use the following Markdown directive to render the fixtures
defined in the OpenAPI `zulip.yaml` for a given endpoint and status
code:

```
{generate_code_example|/messages/render:post|fixture(200)}
```

## Step by step guide

This section offers a step-by-step process for adding documentation
for a new API endpoint.  It assumes you've read and understood the
above.

1. Start by adding [OpenAPI format](../documentation/openapi.html)
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

   You can check your formatting using two helpful tools.
   * `tools/check-openapi` will verify the syntax of `zerver/openapi/zulip.yaml`.
   * `tools/test-backend zerver/tests/test_openapi.py`; this test compares
      your documentation against the code and can find many common
      mistakes in how arguments are declared.

   [rest-api-tutorial]: ../tutorials/writing-views.html#writing-api-rest-endpoints

1. Add a function for the endpoint you'd like to document to
   `zerver/openapi/python_examples.py`. `render_message` is a good
   example to follow.  There are generally two key pieces to your
   test: (1) doing an API query and (2) verifying its result has the
   expected format using `validate_against_openapi_schema`.

1. Make the desired API call inside the function. If our Python
   bindings don't have a dedicated method for a specific API call,
   you may either use `client.call_endpoint` or add a dedicated
   function to the [zulip PyPI
   package](https://github.com/zulip/python-zulip-api/tree/master/zulip).
   Ultimately, the goal is for every endpoint to be documented the
   latter way, but it's useful to be able to write working
   documentation for an endpoint that isn't supported by
   `python-zulip-api` yet.

1. Add the function to the `TEST_FUNCTIONS` dict and one of the
   `test_*` functions at the end of
   `zerver/openapi/python_examples.py`; these will ensure your function
   will be called when running `test-api`.

1. Capture the JSON response returned by the API call (the test
   "fixture").  The easiest way to do this is add an appropriate print
   statement (usually `json.dumps(result, indent=4, sort_keys=True)`),
   and then run `tools/test-api`.  You can also use
   <http://jsonformatter.curiousconcept.com/> to format the JSON
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

1. Finally, write the markdown file for your API endpoint under
   `templates/zerver/api/`.  This is usually pretty easy to template
   off existing endpoints; but refer to the system explanations above
   for details.

1. Add the markdown file to the index in `templates/zerver/help/include/rest-endpoints.md`.

1. Test your endpoint, pretending to be a new user in a hurry.  You
   should make sure that copy-pasting the code in your examples works,
   and post an example of the output in the pull request.

[javascript-examples]: https://github.com/zulip/zulip-js/tree/master/examples

## Why a custom system?

Given that our documentation is written in large part using the
OpenAPI format, why maintain a custom markdown system for displaying
it?  There's several major benefits to this system:

* It is extremely common for API documentation to become out of date
  as an API evolves; this automated testing system helps make it
  possible for Zulip to maintain accurate documentation without a lot
  of manual management.
* Every Zulip server can host correct API documentation for its
  version, with the key variables (like the Zulip server URL) already
  pre-susbtituted for the user.
* We're able to share implementation language and visual styling with
  our Helper Center, which is especially useful for the extensive
  non-REST API documentation pages (e.g. our bot framework).
* Open source systems for displaying OpenAPI documentation (such as
  Swagger) have poor UI, whereas Cloud systems that accept OpenAPI
  data, like readme.io, make the above things much more difficult to
  manage.

Using the standard OpenAPI format gives us flexibility, though; if the
state of third-party tools improves, we don't need to redo most of the
actual documentation work in order to migrate tools.
