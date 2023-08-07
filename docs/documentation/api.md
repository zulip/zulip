# Documenting REST API endpoints

This document explains the system for documenting [Zulip's REST
API](https://zulip.com/api/rest).

Zulip's API documentation is an essential resource both for users and
for the developers of Zulip's mobile and terminal apps. Our vision is
for the documentation to be sufficiently good that developers of
Zulip's apps should never need to look at the server's implementation
to answer questions about the API's semantics.

To achieve these goals, Zulip leverages the popular OpenAPI format as
the data source to ensure that Zulip's API documentation is correct
and remains so as Zulip's API evolves.

In particular, the top goal for this system is that all mistakes in
verifiable content (i.e. not the English explanations) should cause
the Zulip test suite to fail. This is incredibly important, because
once you notice one error in API documentation, you no longer trust it
to be correct, which ends up wasting the time of its users.

Since it's very difficult to not make little mistakes when writing any
untested code, the only good solution to this is a way to test
the documentation. We found dozens of errors in the process of adding
the validation Zulip has today.

Our API documentation is defined by a few sets of files:

- The primary source of our API documentation is the Zulip server's
  [OpenAPI description](openapi.md) at
  `zerver/openapi/zulip.yaml`.
- The documentation is written the same Markdown framework that powers
  our [help center docs](helpcenter.md), with some special
  extensions for rendering nice code blocks and example
  responses. Most API endpoints share a common template,
  `api_docs/api-doc-template.md`, which renders the
  OpenAPI description of the API endpoint. A handful of endpoints that
  require special content, as well as pages that document general API
  details rather than specific endpoints, live at `api_docs/*.md`.
- We have an extensive set of tests designed to validate that the data
  in the OpenAPI file matching the implementation. Specifically,
  `zerver/tests/test_openapi.py` compares every endpoint's accepted
  parameters in `views` code with those declared in `zulip.yaml`. And
  the [backend test suite](../testing/testing-with-django.md) checks
  that every API response served during our extensive backend test
  suite matches one the declared OpenAPI schema for that endpoint.
- The text for the Python examples comes from a test suite for the
  Python API documentation (`zerver/openapi/python_examples.py`; run via
  `tools/test-api`). The `generate_code_example` macro will magically
  read content from that test suite and render it as the code example.
  This structure ensures that Zulip's API documentation is robust to a
  wide range of possible typos and other bugs in the API
  documentation.
- The JavaScript examples are similarly generated and tested using
  `zerver/openapi/javascript_examples.js`.
- The cURL examples are generated and tested using
  `zerver/openapi/curl_param_value_generators.py`.
- The REST API index
  (`api_docs/include/rest-endpoints.md`) in the broader
  /api left sidebar (`api_docs/sidebar_index.md`).

This first section is focused on explaining how the API documentation
system is put together; when actually documenting an endpoint, you'll
want to also read the [Step by step guide](#step-by-step-guide).

## How it works

Let's use the existing documentation for one of our REST API endpoints
to show how the documentation system works:
[POST /messages/render](https://zulip.com/api/render-message).
We highly recommend looking at these resources while reading the above
documentation page:

- `api_docs/api-doc-template.md`
- `zerver/openapi/zulip.yaml`, specifically the section with
  `operationId: render-message`
- `zerver/openapi/python_examples.py`

If you look at the documentation for existing endpoints, you'll notice
that a typical endpoint's documentation is divided into four sections:

- **Title and description**
- **Usage examples**
- **Parameters**
- **Response with examples**

The rest of this guide describes how each of these sections works.

### Title and description

The first line of `api-doc-template.md` generates a lot of key
information for our API endpoint documentation:

```
{generate_api_header(API_ENDPOINT_NAME)}
```

At the top of the endpoint documentation page is the title, and it
comes from the `summary` parameter in the OpenAPI data,
`zerver/openapi/zulip.yaml`.

The endpoint `description` in the OpenAPI data explains what the
endpoint does in clear English. It should include details on how to
use the endpoint correctly or what it's good or bad for, with links
to any alternative endpoints the user might want to consider.

The description should often contain a link to the documentation of
the relevant feature in the [help center](helpcenter.md), and should
include **Changes** notes for all feature level updates documented
in the [API changelog](https://zulip.com/api/changelog), see
`api_docs/changelog.md`, that reference the endpoint.

Endpoints that only administrators can use should be tagged with the
custom `x-requires-administrator` field in the OpenAPI definition.

All of this information is rendered via a Markdown preprocessor,
specifically the `APIHeaderPreprocessor` class defined in
`zerver/openapi/markdown_extension.py`.

### Usage examples

We display usage examples in three languages: Python, JavaScript and
curl; we may add more in the future. Every endpoint should have
Python and curl documentation; JavaScript is optional as we don't
consider that API library to be fully supported.

The examples are defined using a special Markdown extension, see
`zerver/openapi/markdown_extension.py`. Here's the Markdown file
block that uses this in `api-doc-template.md`:

```md
{start_tabs}

{generate_code_example(python)|API_ENDPOINT_NAME|example}

{generate_code_example(javascript)|API_ENDPOINT_NAME|example}

{tab|curl}

{generate_code_example(curl)|API_ENDPOINT_NAME|example}

{end_tabs}
```

In some cases, one wants to configure specific parameters to be
included or excluded from the example curl requests for readability
reasons. One can do that using the `x-curl-examples-parameters`
parameter in the OpenAPI data.

#### Writing Python examples

For the Python examples, you'll write the example in
`zerver/openapi/python_examples.py`, and it'll be run and verified
automatically in Zulip's automated test suite. The code for our
example API endpoint looks like this:

```python
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
`tools/test-api` test suite. The `validate_against_opanapi_schema`
function will verify that the result of that request is as defined in
the examples in `zerver/openapi/zulip.yaml`.

To run as part of the test suite, the `render_message` function needs
to be called from `test_messages` (or one of the other functions at
the bottom of the file). The final function, `test_the_api`, is what
actually runs the tests. Tests with the `openapi_test_function`
decorator that are not called will fail tests, as will new endpoints
that are not covered by an `openapi_test_function`-decorated test.

You will still want to manually test the example using Zulip's Python
API client by copy-pasting from the website; it's easy to make typos
and other mistakes where variables are defined outside the tested
block, and the tests are not foolproof.

The code that renders API documentation pages will extract the block
between the `# {code_example|start}` and `# {code_example|end}` comments,
and substitute it in place of
`{generate_code_example(python)|/messages/render:post|example}`. Note
that here the `API_ENDPOINT_NAME` has been filled in with our example
endpoint's information.

Additional Python imports can be added using the custom
`x-python-examples-extra-imports` field in the OpenAPI definition.

### Parameters

We have a separate Markdown extension to document the parameters that
an API endpoint supports. Implemented in
`zerver/lib/markdown/api_arguments_table_generator.py`, you can see
this in `api-doc-template.md` after the **Parameters** header:

```
{generate_api_arguments_table|zulip.yaml|API_ENDPOINT_NAME}
```

This generates the information from the endpoint's parameter
definition in the OpenAPI data.

Additional content that you'd like to appear in the parameter
description area can be declared using the custom
`x-parameter-description` field in the OpenAPI definition.

### Response with examples

Similar to the parameters section above, there is a separate Markdown
extension to document the endpoint's return values and generate the
example response(s) from the OpenAPI data. Implemented in
`zerver/lib/markdown/api_return_values_table_generator.py`, you can
see this in after the **Response** header in `api-doc-template.md`:

```
{generate_return_values_table|zulip.yaml|API_ENDPOINT_NAME}
```

To generate the example responses from the OpenAPI data, we again
use the special Markdown extension from the **Usage examples**
discussed above, except with the `fixture` argument instead of the
`example` argument:

```
{generate_code_example|API_ENDPOINT_NAME|fixture}
```

Additional content that you'd like to appear in the responses part of
the page can be added using the custom `x-response-description` field
in the OpenAPI definition.

## Step by step guide

This section offers a step-by-step process for adding documentation
for a new API endpoint. It assumes you've read and understood the
above.

1. Start by adding [OpenAPI format](openapi.md)
   data to `zerver/openapi/zulip.yaml` for the endpoint. If you
   copy-paste (which is helpful to get the indentation structure
   right), be sure to update all the content that you copied to
   correctly describe your endpoint!

   In order to do this, you need to figure out how the endpoint in
   question works by reading the code! To understand how arguments
   are specified in Zulip backend endpoints, read our [REST API
   tutorial][rest-api-tutorial], paying special attention to the
   details of `REQ` and `has_request_variables`.

   Once you understand that, the best way to determine the supported
   arguments for an API endpoint is to find the corresponding URL
   pattern in `zprojects/urls.py`, look up the backend function for
   that endpoint in `zerver/views/`, and inspect its arguments
   declared using `REQ`.

   You can check your formatting using these helpful tools.

   - `tools/check-openapi` will verify the syntax of `zerver/openapi/zulip.yaml`.
   - `tools/test-backend zerver/tests/test_openapi.py`; this test compares
     your documentation against the code and can find many common
     mistakes in how arguments are declared.
   - `test-backend`: The full Zulip backend test suite will fail if
     any actual API responses generated by the tests don't match your
     defined OpenAPI schema. Use `test-backend --rerun` for a fast
     edit/refresh cycle when debugging.

   [rest-api-tutorial]: ../tutorials/writing-views.md#writing-api-rest-endpoints

1. Add a function for the endpoint you'd like to document to
   `zerver/openapi/python_examples.py`, decorated with
   `@openapi_test_function`. `render_message` is a good example to
   follow. There are generally two key pieces to your test: (1) doing
   an API query and (2) verifying its result has the expected format
   using `validate_against_openapi_schema`.

1. Make the desired API call inside the function. If our Python
   bindings don't have a dedicated method for a specific API call,
   you may either use `client.call_endpoint` or add a dedicated
   function to the [zulip PyPI
   package](https://github.com/zulip/python-zulip-api/tree/main/zulip).
   Ultimately, the goal is for every endpoint to be documented the
   latter way, but it's useful to be able to write working
   documentation for an endpoint that isn't supported by
   `python-zulip-api` yet.

1. Add the function to one of the `test_*` functions at the end of
   `zerver/openapi/python_examples.py`; this will ensure your
   function will be called when running `test-api`.

1. Capture the JSON response returned by the API call (the test
   "fixture"). The easiest way to do this is add an appropriate print
   statement (usually `json.dumps(result, indent=4, sort_keys=True)`),
   and then run `tools/test-api`. You can also use
   <https://jsonformatter.curiousconcept.com/> to format the JSON
   fixtures. Add the fixture to the `example` subsection of the
   `responses` section for the endpoint in
   `zerver/openapi/zulip.yaml`.

1. Run `./tools/test-api` to make sure your new test function is being
   run and the tests pass.

1. Now, inside the function, isolate the lines of code that call the API and could
   be displayed as a code example. Wrap the relevant lines in
   `# {code_example|start} ... relevant lines go here ... # {code_example|end}`
   comments. The lines inside these comments are what will be displayed as the
   code example on our `/api` page.

1. Finally, if the API docs page of the endpoint doesn't follow the
   common API docs template in
   `api_docs/api-docs-template.md`, then add its custom
   Markdown file under `api_docs/`. However, it is a goal
   to minimize the number of files that diverse from the common
   template, so only do this if there's a good reason.

1. Add the endpoint to the index in
   `api_docs/include/rest-endpoints.md`. The URL should
   match the `operationId` for the endpoint, and the link text should
   match the title of the endpoint from the OpenAPI `summary` field.

1. Test your endpoint, pretending to be a new user in a hurry, by
   visiting it via the links on `http://localhost:9991/api` (the API
   docs are rendered from the Markdown source files on page load, so
   just reload to see an updated version as you edit). You should
   make sure that copy-pasting the code in your examples works, and
   post an example of the output in the pull request.

1. Document the new API in `api_docs/changelog.md` and
   bump the `API_FEATURE_LEVEL` in `version.py`. Also, make sure to
   add a `**Changes**` entry in the description of the new API/event
   in `zerver/openapi/zulip.yaml`, which mentions the API feature level
   at which they were added.

## Why a custom system?

Given that our documentation is written in large part using the
OpenAPI format, why maintain a custom Markdown system for displaying
it? There's several major benefits to this system:

- It is extremely common for API documentation to become out of date
  as an API evolves; this automated testing system helps make it
  possible for Zulip to maintain accurate documentation without a lot
  of manual management.
- Every Zulip server can host correct API documentation for its
  version, with the key variables (like the Zulip server URL) already
  pre-substituted for the user.
- We're able to share implementation language and visual styling with
  our Help Center, which is especially useful for the extensive
  non-REST API documentation pages (e.g. our bot framework).

Using the standard OpenAPI format gives us flexibility, though; if we
later choose to migrate to third-party tools, we don't need to redo
the actual documentation work in order to migrate tools.

## Debugging schema validation errors

A common function used to validate and test Zulip's REST API is
`validate_against_openapi_schema`. It is used to verify that every
successful API response returned in the backend and documentation test
suites are a documented possibility in the API documentation.

Therefore, when you add a new feature or setting to Zulip, you will most
likely need to update the API documentation (`zerver/openapi/zulip.yaml`)
in order to pass existing tests that use this function. Additionally, if
you're writing documentation for a new or undocumented REST API endpoint,
you'll want to use this function to validate and test your changes in
`zerver/openapi/python_examples.py`.

Below are some examples to help you when debugging the schema validation
errors produced by `validate_against_openapi_schema`. Before reading
through the examples, we recommend reviewing the
[OpenAPI configuration](openapi.md) documentation if you're unfamiliar
with the format.

If you use Visual Studio Code, an OpenAPI extension can be very helpful in
navigating Zulip's large and detailed OpenAPI file; see
`.vscode/extensions.json`.

### Deconstructing the error output

To start with a clear example, let's imagine that we are writing the
documentation for the REST API endpoint for uploading a file,
[POST /api/v1/user_uploads](https://zulip.com/api/upload-file).

There are no parameters for this endpoint, and only one return value
specific to this endpoint, `uri`, which is the URL of the uploaded file.
If we comment out that return value and example from the existing API
documentation in `zerver/openapi/zulip.yaml`, e.g.:

```yaml
  /user_uploads:
    post:
      operationId: upload-file
...
      responses:
        "200":
          description: Success.
          content:
            application/json:
              schema:
                allOf:
                  - $ref: "#/components/schemas/JsonSuccessBase"
                  - additionalProperties: false
                    properties:
                      result: {}
                      msg: {}
                      # uri:
                      #   type: string
                      #   description: |
                      #     The URI of the uploaded file.
                    example:
                      {
                        "msg": "",
                        "result": "success",
                        # "uri": "/user_uploads/1/4e/m2A3MSqFnWRLUf9SaPzQ0Up_/zulip.txt",
                      }
```

We will now get an error when we run the API documentation test suite
in the development environment (`tools/test-api`):

```console
Running API tests...
2022-12-19 15:05:42.347 WARN [django.server] "POST /api/v1/users HTTP/1.1" 400 88
Waiting for children to stop...
Traceback (most recent call last):
  File "tools/test-api", line 93, in <module>
    test_the_api(client, nonadmin_client, owner_client)
  File "/srv/zulip/zerver/openapi/python_examples.py", line 1636, in test_the_api
    test_users(client, owner_client)
  File "/srv/zulip/zerver/openapi/python_examples.py", line 1555, in test_users
    upload_file(client)
  File "/srv/zulip/zerver/openapi/python_examples.py", line 52, in _record_calls_wrapper
    return test_func(*args, **kwargs)
  File "/srv/zulip/zerver/openapi/python_examples.py", line 1284, in upload_file
    validate_against_openapi_schema(result, "/user_uploads", "post", "200")
  File "/srv/zulip/zerver/openapi/openapi.py", line 489, in validate_against_openapi_schema
    raise SchemaError(message) from None
zerver.openapi.openapi.SchemaError: 1 response validation error(s) at post /api/v1/user_uploads (200):

ValidationError: Additional properties are not allowed ('uri' was unexpected)

Failed validating 'additionalProperties' in schema['allOf'][2]:
    {'additionalProperties': False,
     'example': {'msg': '',
                 'result': 'success',
     'properties': {'msg': {}, 'result': {}}}

On instance:
    {'msg': '',
     'result': 'success',
     'uri': '/user_uploads/2/85/XoqF0K7XEOLVGylgdpof80RB/img.jpg'}

```

We can see in the traceback that a `SchemaError` was raised in
`validate_against_openapi_schema`:

```console
  File "/srv/zulip/zerver/openapi/openapi.py", line 478, in validate_against_openapi_schema
    raise SchemaError(message) from None
```

The next line in the output, let's us know how many errors were found
and for what endpoint.

```console
zerver.openapi.openapi.SchemaError: 1 response validation error(s) at post /api/v1/user_uploads (200):
```

As expected from commenting out the code above, there was one validation
error for the `POST /api/v1/user_uploads` endpoint. The next line gives
more information about that error.

```console
ValidationError: Additional properties are not allowed ('uri' was unexpected)
```

We see that there was a `uri` value returned by the endpoint that hasn't
been documented. The next few lines of output, show us what return values
are documented (again due to our changes) for this endpoint.

```console
Failed validating 'additionalProperties' in schema['allOf'][2]:
    {'additionalProperties': False,
     'example': {'msg': '',
                 'result': 'success',
     'properties': {'msg': {}, 'result': {}}}
```

And finally, we see the test instance that did not match our current
documentation, which includes the `uri` return value.

```console
On instance:
    {'msg': '',
     'result': 'success',
     'uri': '/user_uploads/2/85/XoqF0K7XEOLVGylgdpof80RB/img.jpg'}
```

This is a useful example because the endpoint's documentation is short
and straightforward, helping to easily identify the parts of the
error output that are useful in debugging these errors when testing the
API documentation.

### Adding a realm setting

Building on [the new feature tutorial](../tutorials/new-feature-tutorial.md)
example, if the realm setting for `mandatory_topics` was not documented
in the `POST /api/v1/register` endpoint, running `tools/test-api` in the
development environment would result in this error:

```console
...
zerver.openapi.openapi.SchemaError: 1 response validation error(s) at post /api/v1/register (200):

ValidationError: Additional properties are not allowed ('realm_mandatory_topics' was unexpected)

Failed validating 'additionalProperties' in schema['allOf'][2]:
    'OpenAPI schema omitted due to length of output.'

On instance:
    'Error instance omitted due to length of output.'
```

Because this endpoint is very long and descriptive, we do not print the
entire documentation schema (or test instance, in this case) to the
console. Doing so would print thousands of lines of output that are not
useful for debugging what is missing from the API documentation.

The key information for debugging this endpoint is in the line beginning
with `ValidationError`. There we can see that the documentation does not
include the new `realm_mandatory_topics` boolean that we added in the
example feature tutorial, and we can look at other similar realm settings
to add the documentation for that new feature.
