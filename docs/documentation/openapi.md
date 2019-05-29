# OpenAPI REST API documentation

The [OpenAPI](http://swagger.io/specification/) (formerly known as
Swagger) specification is a standardized way to describe how an API
functions. This description then can then be used by any tool that
supports the standard.

Zulip uses the Swagger spec to generate an API reference from the
`zulip.yaml` file. This page is a basic introduction to the format of
this file and how to add content to it.

In a Swagger file, every configuration section is an object. Objects
may contain other objects, or reference objects defined
elsewhere. Larger API specifications may be split into multiple
files. There are more types of objects than mentioned here, you can
find the complete details at
[Swagger/OpenAPI specification page](http://swagger.io/specification).

This library isn't in production use yet, but it is our current plan
for how Zulip's API documentation will work.

## Working with the `zulip.yaml` file

A Swagger specification file has three general parts: information and
configuration, endpoint definitions, and object schemas referenced by
other objects (as an alternative to defining everything inline.)
References can either specify an individual object, using `$ref:`, or
compose a larger definition from individual objects with `allOf:`
(which may itself contain a `$ref`.)

### Configuration

These objects, at the top of `zulip.yaml`, identify the API, define
the backend host for the working examples, list supported schemes and
types of authentication, and configure other settings. Once defined,
information in this section rarely changes.

For example, the `swagger` and `info` objects look like this:
```
# Basic Swagger UI info
swagger: '2.0'
info:
  version: '1.0.0'
  title: Zulip REST API
  description: Powerful open source group chat
  contact:
    url: https://zulip.org/
  license:
    name: Apache 2.0
    url: https://www.apache.org/licenses/LICENSE-2.0.html
```

### Endpoint definitions

The [Paths Object](http://swagger.io/specification/#pathsObject)
contains
[Path Item Objects](http://swagger.io/specification/#pathItemObject)
for each endpoint. It describes in detail the methods and parameters
the endpoint accepts and responses it returns.

There is one Path Item Object for each supported method, containing a
[Parameters Definition Object](http://swagger.io/specification/#parametersDefinitionObject)
describing the required and optional inputs. A
[Response Object](http://swagger.io/specification/#responseObject)
similarly specifies the content of the response. They may reference
schemas from a global Definitions Object (see [Schemas](#schemas),
below.)

Example:

The `/users/{user}/presence` endpoint (defined in a
[Path Item Object](http://swagger.io/specification/#pathItemObject))
expects a GET request with one
[parameter](http://swagger.io/specification/#parameterObject), HTTP
Basic authentication, and returns a JSON response containing `msg`,
`result`, and `presence` values.

```
/users/{user}/presence:
  get:
    description: Get presence data for another user.
    operationId: getPresence
    parameters:
    - name: user
      in: path
      description: Enter email address
      required: true
      type: string
    security:
    - basicAuth: []
    responses:
      '200':
        description: The response from a successful call
        schema:
          type: object
          required:
          - msg
          - result
          - presence
          properties:
            msg:
              type: string
            result:
              type: string
            presence:
              type: array
```

### Schemas

The
[Definitions Object](http://swagger.io/specification/#definitionsObject)
contains schemas referenced by other objects. For example,
`MessageResponse`, the response from the `/messages` endpoint,
contains three required parameters.  Two are strings, and one is an
integer.

```
MessageResponse:
  type: object
  required:
    - msg
    - result
    - id
  properties:
    msg:
      type: string
    result:
      type: string
    id:
      type: integer
      format: int64
```

You can find more examples, including GET requests and nested objects, in
`/static/yaml/zulip.yaml`.

## Zulip Swagger YAML style:

We're collecting decisions we've made on how our Swagger YAML files
should be organized here:

* Use shared definitions and YAML anchors to avoid duplicating content
  where possible.

## Tips for working with YAML:

You can edit YAML files in any text editor. Indentation defines
blocks, so whitespace is important (as it is in Python.) TAB
characters are not permitted.  If your editor has an option to replace
tabs with spaces, this is helpful.

You can also use the
[Swagger Editor](http://swagger.io/swagger-editor), which validates
YAML and understands the Swagger specification. Download and run it
locally, or use the online version. If you aren't using a YAML-aware
editor, make small changes and check your additions often.

Note: if you are working with
[Swagger UI](http://swagger.io/swagger-ui/) in a local development
environment, it uses an online validator that must be able to access
your file. You may see a red "ERROR" button at the bottom of your API
docs page instead of the green "VALID" one even if your file is
correct.

### Formatting help:

* Comments begin with a # character.

* Descriptions do not need to be in quotes, and may use common
  Markdown format options like inline code \` (backtick) and `#`
  headings.

* A single `|` (pipe) character begins a multi-line description on the
  next line.  Single spaced lines (one newline at the end of each) are
  joined. Use an extra blank line for a paragraph break.

### Examples:

```
Description: This is a single line description.
```

```
Description: |
             This description has multiple lines.
             Sometimes descriptions can go on for
             several sentences.

             A description might have multiple paragraphs
             as well.
```
