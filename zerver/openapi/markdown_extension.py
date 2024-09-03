# Zulip's OpenAPI-based API documentation system is documented at
#   https://zulip.readthedocs.io/en/latest/documentation/api.html
#
# This file defines the special Markdown extension that is used to
# render the code examples, example responses, etc. that appear in
# Zulip's public API documentation.

import inspect
import json
import re
import shlex
from collections.abc import Mapping
from re import Match, Pattern
from textwrap import dedent
from typing import Any

import markdown
from django.conf import settings
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from typing_extensions import override

import zerver.openapi.python_examples
from zerver.lib.markdown.priorities import PREPROCESSOR_PRIORITIES
from zerver.openapi.openapi import (
    NO_EXAMPLE,
    Parameter,
    check_additional_imports,
    check_requires_administrator,
    generate_openapi_fixture,
    get_curl_include_exclude,
    get_openapi_description,
    get_openapi_parameters,
    get_openapi_summary,
    get_parameters_description,
    get_responses_description,
    openapi_spec,
)

API_ENDPOINT_NAME = r"/[a-z_\-/-{}]+:[a-z]+"
API_LANGUAGE = r"\w+"
API_KEY_TYPE = r"fixture|example"
MACRO_REGEXP = re.compile(
    rf"""
        {{
          generate_code_example
          (?: \( \s* ({API_LANGUAGE}) \s* \) )?
          \|
          \s* ({API_ENDPOINT_NAME}) \s*
          \|
          \s* ({API_KEY_TYPE}) \s*
        }}
    """,
    re.VERBOSE,
)
PYTHON_EXAMPLE_REGEX = re.compile(r"\# \{code_example\|\s*(start|end)\s*\}")
JS_EXAMPLE_REGEX = re.compile(r"\/\/ \{code_example\|\s*(start|end)\s*\}")
MACRO_REGEXP_HEADER = re.compile(rf"{{generate_api_header\(\s*({API_ENDPOINT_NAME})\s*\)}}")
MACRO_REGEXP_RESPONSE_DESC = re.compile(
    rf"{{generate_response_description\(\s*({API_ENDPOINT_NAME})\s*\)}}"
)
MACRO_REGEXP_PARAMETER_DESC = re.compile(
    rf"{{generate_parameter_description\(\s*({API_ENDPOINT_NAME})\s*\)}}"
)

PYTHON_CLIENT_CONFIG = """
#!/usr/bin/env python3

import zulip

# Pass the path to your zuliprc file here.
client = zulip.Client(config_file="~/zuliprc")

"""

PYTHON_CLIENT_ADMIN_CONFIG = """
#!/usr/bin/env python

import zulip

# The user for this zuliprc file must be an organization administrator
client = zulip.Client(config_file="~/zuliprc-admin")

"""

JS_CLIENT_CONFIG = """
const zulipInit = require("zulip-js");

// Pass the path to your zuliprc file here.
const config = { zuliprc: "zuliprc" };

"""

JS_CLIENT_ADMIN_CONFIG = """
const zulipInit = require("zulip-js");

// The user for this zuliprc file must be an organization administrator.
const config = { zuliprc: "zuliprc-admin" };

"""

DEFAULT_AUTH_EMAIL = "BOT_EMAIL_ADDRESS"
DEFAULT_AUTH_API_KEY = "BOT_API_KEY"
DEFAULT_EXAMPLE = {
    "integer": 1,
    "string": "demo",
    "boolean": False,
}
ADMIN_CONFIG_LANGUAGES = ["python", "javascript"]


def extract_code_example(
    source: list[str], snippet: list[Any], example_regex: Pattern[str]
) -> list[Any]:
    start = -1
    end = -1
    for line in source:
        match = example_regex.search(line)
        if match:
            if match.group(1) == "start":
                start = source.index(line)
            elif match.group(1) == "end":
                end = source.index(line)
                break

    if start == -1 and end == -1:
        return snippet

    snippet.append(source[start + 1 : end])
    source = source[end + 1 :]
    return extract_code_example(source, snippet, example_regex)


def render_python_code_example(
    function: str, admin_config: bool = False, **kwargs: Any
) -> list[str]:
    if function not in zerver.openapi.python_examples.TEST_FUNCTIONS:
        return []
    method = zerver.openapi.python_examples.TEST_FUNCTIONS[function]
    function_source_lines = inspect.getsourcelines(method)[0]

    if admin_config:
        config_string = PYTHON_CLIENT_ADMIN_CONFIG
    else:
        config_string = PYTHON_CLIENT_CONFIG

    endpoint, endpoint_method = function.split(":")
    extra_imports = check_additional_imports(endpoint, endpoint_method)
    if extra_imports:
        extra_imports = sorted([*extra_imports, "zulip"])
        extra_imports = [f"import {each_import}" for each_import in extra_imports]
        config_string = config_string.replace("import zulip", "\n".join(extra_imports))

    config = config_string.splitlines()

    snippets = extract_code_example(function_source_lines, [], PYTHON_EXAMPLE_REGEX)

    return [
        "{tab|python}\n",
        "```python",
        *config,
        # Remove one level of indentation and strip newlines
        *(line.removeprefix("    ").rstrip() for snippet in snippets for line in snippet),
        "print(result)",
        "\n",
        "```",
    ]


def render_javascript_code_example(
    function: str, admin_config: bool = False, **kwargs: Any
) -> list[str]:
    pattern = rf'^add_example\(\s*"[^"]*",\s*{re.escape(json.dumps(function))},\s*\d+,\s*async \(client, console\) => \{{\n(.*?)^(?:\}}| *\}},\n)\);$'
    with open("zerver/openapi/javascript_examples.js") as f:
        m = re.search(pattern, f.read(), re.MULTILINE | re.DOTALL)
    if m is None:
        return []
    function_source_lines = dedent(m.group(1)).splitlines()

    snippets = extract_code_example(function_source_lines, [], JS_EXAMPLE_REGEX)

    if admin_config:
        config = JS_CLIENT_ADMIN_CONFIG.splitlines()
    else:
        config = JS_CLIENT_CONFIG.splitlines()

    code_example = [
        "{tab|js}\n",
        "More examples and documentation can be found [here](https://github.com/zulip/zulip-js).",
    ]

    code_example.append("```js")
    code_example.extend(config)
    code_example.append("(async () => {")
    code_example.append("    const client = await zulipInit(config);")
    for snippet in snippets:
        code_example.append("")
        # Strip newlines
        code_example.extend("    " + line.rstrip() for line in snippet)
    code_example.append("})();")

    code_example.append("```")

    return code_example


def curl_method_arguments(endpoint: str, method: str, api_url: str) -> list[str]:
    # We also include the -sS verbosity arguments here.
    method = method.upper()
    url = f"{api_url}/v1{endpoint}"
    valid_methods = ["GET", "POST", "DELETE", "PUT", "PATCH", "OPTIONS"]
    if method == "GET":
        # Then we need to make sure that each -d option translates to becoming
        # a GET parameter (in the URL) and not a POST parameter (in the body).
        # TODO: remove the -X part by updating the linting rule. It's redundant.
        return ["-sSX", "GET", "-G", url]
    elif method in valid_methods:
        return ["-sSX", method, url]
    else:
        msg = f"The request method {method} is not one of {valid_methods}"
        raise ValueError(msg)


def get_openapi_param_example_value_as_string(
    endpoint: str, method: str, parameter: Parameter, curl_argument: bool = False
) -> str:
    if "type" in parameter.value_schema:
        param_type = parameter.value_schema["type"]
    else:
        # Hack: Ideally, we'd extract a common function for handling
        # oneOf values in types and do something with the resulting
        # union type.  But for this logic's purpose, it's good enough
        # to just check the first parameter.
        param_type = parameter.value_schema["oneOf"][0]["type"]

    if param_type in ["object", "array"]:
        if parameter.example is NO_EXAMPLE:
            msg = f"""All array and object type request parameters must have
concrete examples. The openAPI documentation for {endpoint}/{method} is missing an example
value for the {parameter.name} parameter. Without this we cannot automatically generate a
cURL example."""
            raise ValueError(msg)
        ordered_ex_val_str = json.dumps(parameter.example, sort_keys=True)
        # We currently don't have any non-JSON encoded arrays.
        assert parameter.json_encoded
        if curl_argument:
            return "    --data-urlencode " + shlex.quote(f"{parameter.name}={ordered_ex_val_str}")
        return ordered_ex_val_str  # nocoverage
    else:
        if parameter.example is NO_EXAMPLE:
            example_value = DEFAULT_EXAMPLE[param_type]
        else:
            example_value = parameter.example

        # Booleans are effectively JSON-encoded, in that we pass
        # true/false, not the Python str(True) = "True"
        if parameter.json_encoded or isinstance(example_value, bool | float | int):
            example_value = json.dumps(example_value)
        else:
            assert isinstance(example_value, str)

        if curl_argument:
            return "    --data-urlencode " + shlex.quote(f"{parameter.name}={example_value}")
        return example_value


def generate_curl_example(
    endpoint: str,
    method: str,
    api_url: str,
    auth_email: str = DEFAULT_AUTH_EMAIL,
    auth_api_key: str = DEFAULT_AUTH_API_KEY,
    exclude: list[str] | None = None,
    include: list[str] | None = None,
) -> list[str]:
    lines = ["```curl"]
    operation = endpoint + ":" + method.lower()
    operation_entry = openapi_spec.openapi()["paths"][endpoint][method.lower()]
    global_security = openapi_spec.openapi()["security"]

    parameters = get_openapi_parameters(endpoint, method)
    operation_request_body = operation_entry.get("requestBody", None)
    operation_security = operation_entry.get("security", None)

    if settings.RUNNING_OPENAPI_CURL_TEST:  # nocoverage
        from zerver.openapi.curl_param_value_generators import patch_openapi_example_values

        parameters, operation_request_body = patch_openapi_example_values(
            operation, parameters, operation_request_body
        )

    format_dict = {}
    for parameter in parameters:
        if parameter.kind != "path":
            continue
        example_value = get_openapi_param_example_value_as_string(endpoint, method, parameter)
        format_dict[parameter.name] = example_value
    example_endpoint = endpoint.format_map(format_dict)

    curl_first_line_parts = ["curl", *curl_method_arguments(example_endpoint, method, api_url)]
    lines.append(shlex.join(curl_first_line_parts))

    insecure_operations = ["/dev_fetch_api_key:post", "/fetch_api_key:post"]
    if operation_security is None:
        if global_security == [{"basicAuth": []}]:
            authentication_required = True
        else:
            raise AssertionError(
                "Unhandled global securityScheme. Please update the code to handle this scheme."
            )
    elif operation_security == []:
        if operation in insecure_operations:
            authentication_required = False
        else:
            raise AssertionError(
                "Unknown operation without a securityScheme. Please update insecure_operations."
            )
    else:
        raise AssertionError(
            "Unhandled securityScheme. Please update the code to handle this scheme."
        )

    if authentication_required:
        lines.append("    -u " + shlex.quote(f"{auth_email}:{auth_api_key}"))

    for parameter in parameters:
        if parameter.kind == "path":
            continue

        if include is not None and parameter.name not in include:
            continue

        if exclude is not None and parameter.name in exclude:
            continue

        example_value = get_openapi_param_example_value_as_string(
            endpoint, method, parameter, curl_argument=True
        )
        lines.append(example_value)

    if "requestBody" in operation_entry and "multipart/form-data" in (
        content := operation_entry["requestBody"]["content"]
    ):
        properties = content["multipart/form-data"]["schema"]["properties"]
        for key, property in properties.items():
            lines.append("    -F " + shlex.quote("{}=@{}".format(key, property["example"])))

    for i in range(1, len(lines) - 1):
        lines[i] += " \\"

    lines.append("```")

    return lines


def render_curl_example(
    function: str,
    api_url: str,
    admin_config: bool = False,
) -> list[str]:
    """A simple wrapper around generate_curl_example."""
    parts = function.split(":")
    endpoint = parts[0]
    method = parts[1]
    kwargs: dict[str, Any] = {}
    if len(parts) > 2:
        kwargs["auth_email"] = parts[2]
    if len(parts) > 3:
        kwargs["auth_api_key"] = parts[3]
    kwargs["api_url"] = api_url
    rendered_example = []
    for element in get_curl_include_exclude(endpoint, method):
        kwargs["include"] = None
        kwargs["exclude"] = None
        if element["type"] == "include":
            kwargs["include"] = element["parameters"]["enum"]
        if element["type"] == "exclude":
            kwargs["exclude"] = element["parameters"]["enum"]
        if "description" in element:
            rendered_example.extend(element["description"].splitlines())
        rendered_example += generate_curl_example(endpoint, method, **kwargs)
    return rendered_example


SUPPORTED_LANGUAGES: dict[str, Any] = {
    "python": {
        "client_config": PYTHON_CLIENT_CONFIG,
        "admin_config": PYTHON_CLIENT_ADMIN_CONFIG,
        "render": render_python_code_example,
    },
    "curl": {
        "render": render_curl_example,
    },
    "javascript": {
        "client_config": JS_CLIENT_CONFIG,
        "admin_config": JS_CLIENT_ADMIN_CONFIG,
        "render": render_javascript_code_example,
    },
}


class APIMarkdownExtension(Extension):
    def __init__(self, api_url: str | None) -> None:
        self.config = {
            "api_url": [
                api_url,
                "API URL to use when rendering curl examples",
            ],
        }

    @override
    def extendMarkdown(self, md: markdown.Markdown) -> None:
        md.preprocessors.register(
            APICodeExamplesPreprocessor(md, self.getConfigs()),
            "generate_code_example",
            PREPROCESSOR_PRIORITIES["generate_code_example"],
        )
        md.preprocessors.register(
            APIHeaderPreprocessor(md, self.getConfigs()),
            "generate_api_header",
            PREPROCESSOR_PRIORITIES["generate_api_header"],
        )
        md.preprocessors.register(
            ResponseDescriptionPreprocessor(md, self.getConfigs()),
            "generate_response_description",
            PREPROCESSOR_PRIORITIES["generate_response_description"],
        )
        md.preprocessors.register(
            ParameterDescriptionPreprocessor(md, self.getConfigs()),
            "generate_parameter_description",
            PREPROCESSOR_PRIORITIES["generate_parameter_description"],
        )


class BasePreprocessor(Preprocessor):
    def __init__(
        self, regexp: Pattern[str], md: markdown.Markdown, config: Mapping[str, Any]
    ) -> None:
        super().__init__(md)
        self.api_url = config["api_url"]
        self.REGEXP = regexp

    @override
    def run(self, lines: list[str]) -> list[str]:
        done = False
        while not done:
            for line in lines:
                loc = lines.index(line)
                match = self.REGEXP.search(line)

                if match:
                    text = self.generate_text(match)

                    # The line that contains the directive to include the macro
                    # may be preceded or followed by text or tags, in that case
                    # we need to make sure that any preceding or following text
                    # stays the same.
                    line_split = self.REGEXP.split(line, maxsplit=0)
                    preceding = line_split[0]
                    following = line_split[-1]
                    text = [preceding, *text, following]
                    lines = lines[:loc] + text + lines[loc + 1 :]
                    break
            else:
                done = True
        return lines

    def generate_text(self, match: Match[str]) -> list[str]:
        function = match.group(1)
        text = self.render(function)
        return text

    def render(self, function: str) -> list[str]:
        raise NotImplementedError("Must be overridden by a child class")


class APICodeExamplesPreprocessor(BasePreprocessor):
    def __init__(self, md: markdown.Markdown, config: Mapping[str, Any]) -> None:
        super().__init__(MACRO_REGEXP, md, config)

    @override
    def generate_text(self, match: Match[str]) -> list[str]:
        language = match.group(1) or ""
        function = match.group(2)
        key = match.group(3)
        if self.api_url is None:
            raise AssertionError("Cannot render curl API examples without API URL set.")

        if key == "fixture":
            text = self.render(function)
        elif key == "example":
            path, method = function.rsplit(":", 1)
            admin_config = language in ADMIN_CONFIG_LANGUAGES and check_requires_administrator(
                path, method
            )
            text = SUPPORTED_LANGUAGES[language]["render"](
                function, api_url=self.api_url, admin_config=admin_config
            )
        return text

    @override
    def render(self, function: str) -> list[str]:
        path, method = function.rsplit(":", 1)
        return generate_openapi_fixture(path, method)


class APIHeaderPreprocessor(BasePreprocessor):
    def __init__(self, md: markdown.Markdown, config: Mapping[str, Any]) -> None:
        super().__init__(MACRO_REGEXP_HEADER, md, config)

    @override
    def render(self, function: str) -> list[str]:
        path, method = function.rsplit(":", 1)
        raw_title = get_openapi_summary(path, method)
        description_dict = get_openapi_description(path, method)
        return [
            *("# " + line for line in raw_title.splitlines()),
            *(["{!api-admin-only.md!}"] if check_requires_administrator(path, method) else []),
            "",
            f"`{method.upper()} {self.api_url}/v1{path}`",
            "",
            *description_dict.splitlines(),
        ]


class ResponseDescriptionPreprocessor(BasePreprocessor):
    def __init__(self, md: markdown.Markdown, config: Mapping[str, Any]) -> None:
        super().__init__(MACRO_REGEXP_RESPONSE_DESC, md, config)

    @override
    def render(self, function: str) -> list[str]:
        path, method = function.rsplit(":", 1)
        raw_description = get_responses_description(path, method)
        return raw_description.splitlines()


class ParameterDescriptionPreprocessor(BasePreprocessor):
    def __init__(self, md: markdown.Markdown, config: Mapping[str, Any]) -> None:
        super().__init__(MACRO_REGEXP_PARAMETER_DESC, md, config)

    @override
    def render(self, function: str) -> list[str]:
        path, method = function.rsplit(":", 1)
        raw_description = get_parameters_description(path, method)
        return raw_description.splitlines()


def makeExtension(*args: Any, **kwargs: str) -> APIMarkdownExtension:
    return APIMarkdownExtension(*args, **kwargs)
