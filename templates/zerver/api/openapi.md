# OpenAPI

[OpenAPI][openapi-spec] is a popular format for describing an API. An
OpenAPI file can be used by various tools to generate documentation
for the API or even basic client-side bindings for dozens of
programming languages.

Zulip's API is described in [zerver/openapi/zulip.yaml](https://raw.githubusercontent.com/zulip/zulip/main/zerver/openapi/zulip.yaml). Our aim is for that file to fully describe every endpoint in the Zulip API, and
for the Zulip test suite to fail should the API every change without a
corresponding adjustment to the documentation. In particular,
essentially all content in Zulip's [REST API
documentation](https://zulip.readthedocs.io/en/latest/documentation/api.html)
is generated from our OpenAPI file.

In an OpenAPI file, every configuration section is an object.
Objects may contain other objects, or reference objects defined
elsewhere. Larger API specifications may be split into multiple
files. See the [OpenAPI specification][openapi-spec].

[openapi-spec]: https://github.com/OAI/OpenAPI-Specification/#the-openapi-specification

