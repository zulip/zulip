# The Zulip REST API

The Zulip REST API powers the Zulip web and mobile apps, so anything
you can do in Zulip, you can do with Zulip's REST API.  To use this API:

* You'll need to [get an API key](/api/api-keys).  You will likely
  want to create a bot, unless you're using the API to interact with
  your own account (e.g. exporting your personal message history).
* Choose what language you'd like to use.  You can download the
  [Python or JavaScript bindings](/api/installation-instructions), or
  just make HTTP request with your favorite programming language.  If
  you're making your own HTTP requests, you'll want to send the
  appropriate HTTP Basic Authentication headers; see each endpoint's
  `curl` option for details on the request format.
* The Zulip API has a standard
  [system for reporting errors](/api/rest_error_handling).

Most other details are covered in the documentation for the individual
endpoints:

{!rest_endpoints.md!}

Since Zulip is open source, you can also consult the
[Zulip server source code](https://github.com/zulip/zulip/) as a
workaround for how to do anything not documented here.
