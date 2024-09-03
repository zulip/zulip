import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

import markdown
from django.utils.html import escape as escape_html
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from typing_extensions import override

from zerver.lib.markdown.priorities import PREPROCESSOR_PRIORITIES
from zerver.openapi.openapi import (
    Parameter,
    check_deprecated_consistency,
    get_openapi_parameters,
    get_parameters_description,
)

REGEXP = re.compile(r"\{generate_api_arguments_table\|\s*(.+?)\s*\|\s*(.+)\s*\}")

API_PARAMETER_TEMPLATE = """
<div class="api-argument" id="parameter-{argument}">
    <p class="api-argument-name"><strong>{argument}</strong> <span class="api-field-type">{type}</span> {required} {deprecated} <a href="#parameter-{argument}" class="api-argument-hover-link"><i class="fa fa-chain"></i></a></p>
    <div class="api-example">
        <span class="api-argument-example-label">Example</span>: <code>{example}</code>
    </div>
    <div class="api-description">{description}{object_details}</div>
    <hr>
</div>
""".strip()

OBJECT_DETAILS_TEMPLATE = """
<p><strong>{argument}</strong> object details:</p>
<ul>
{values}
</ul>
""".strip()

ONEOF_OBJECT_DETAILS_TEMPLATE = """
<p>An object with the following fields:</p>
<ul>
{values}
</ul>
""".strip()

OBJECT_LIST_ITEM_TEMPLATE = """
<li>
<code>{value}</code>: <span class=api-field-type>{data_type}</span> {required} {description}{object_details}
</li>
""".strip()

OBJECT_DESCRIPTION_TEMPLATE = """
{description}
<p>{additional_information}</p>
""".strip()

OBJECT_CODE_TEMPLATE = "<code>{value}</code>".strip()

ONEOF_DETAILS_TEMPLATE = """
<p>This parameter must be one of the following:</p>
<ol>
{values}
</ol>
""".strip()

ONEOF_LIST_ITEM_TEMPLATE = """
<li>{item}</li>
""".strip()


class MarkdownArgumentsTableGenerator(Extension):
    @override
    def extendMarkdown(self, md: markdown.Markdown) -> None:
        md.preprocessors.register(
            APIArgumentsTablePreprocessor(md, self.getConfigs()),
            "generate_api_arguments",
            PREPROCESSOR_PRIORITIES["generate_api_arguments"],
        )


class APIArgumentsTablePreprocessor(Preprocessor):
    def __init__(self, md: markdown.Markdown, config: Mapping[str, Any]) -> None:
        super().__init__(md)

    @override
    def run(self, lines: list[str]) -> list[str]:
        done = False
        while not done:
            for line in lines:
                loc = lines.index(line)
                match = REGEXP.search(line)

                if not match:
                    continue

                doc_name = match.group(2)
                endpoint, method = doc_name.rsplit(":", 1)
                parameters = get_openapi_parameters(endpoint, method)
                if parameters:
                    text = self.render_parameters(parameters)
                # We want to show this message only if the parameters
                # description doesn't say anything else.
                elif get_parameters_description(endpoint, method) == "":
                    text = ["This endpoint does not accept any parameters."]
                else:
                    text = []
                # The line that contains the directive to include the macro
                # may be preceded or followed by text or tags, in that case
                # we need to make sure that any preceding or following text
                # stays the same.
                line_split = REGEXP.split(line, maxsplit=0)
                preceding = line_split[0]
                following = line_split[-1]
                text = [preceding, *text, following]
                lines = lines[:loc] + text + lines[loc + 1 :]
                break
            else:
                done = True
        return lines

    def render_oneof_block(self, object_schema: dict[str, Any], name: str) -> str:
        md_engine = markdown.Markdown(extensions=[])
        content = ""
        for element in object_schema["oneOf"]:
            if "items" in element and "properties" in element["items"]:
                content += ONEOF_LIST_ITEM_TEMPLATE.format(
                    item=self.render_object_details(element["items"], str(name), True)
                )
            elif "properties" in element:
                content += ONEOF_LIST_ITEM_TEMPLATE.format(
                    item=self.render_object_details(element, str(name), True)
                )
            elif "description" in element:
                content += ONEOF_LIST_ITEM_TEMPLATE.format(
                    item=md_engine.convert(element["description"])
                )
        return ONEOF_DETAILS_TEMPLATE.format(values=content)

    def render_parameters(self, parameters: Sequence[Parameter]) -> list[str]:
        lines = []

        md_engine = markdown.Markdown(extensions=[])
        parameters = sorted(parameters, key=lambda parameter: parameter.deprecated)
        for parameter in parameters:
            name = parameter.name
            description = parameter.description
            enums = parameter.value_schema.get("enum")
            if enums is not None:
                formatted_enums = [
                    OBJECT_CODE_TEMPLATE.format(value=json.dumps(enum)) for enum in enums
                ]
                description += "\nMust be one of: {}. ".format(", ".join(formatted_enums))

            default = parameter.value_schema.get("default")
            if default is not None:
                description += f"\nDefaults to `{json.dumps(default)}`."
            data_type = generate_data_type(parameter.value_schema)

            # TODO: OpenAPI allows indicating where the argument goes
            # (path, querystring, form data...).  We should document this detail.

            # We use this style without explicit JSON encoding for
            # integers, strings, and booleans.
            # * For booleans, JSON encoding correctly corrects for Python's
            #   str(True)="True" not matching the encoding of "true".
            # * For strings, doing so nicely results in strings being quoted
            #   in the documentation, improving readability.
            # * For integers, it is a noop, since json.dumps(3) == str(3) == "3".
            example = json.dumps(parameter.example)

            required_string: str = "required"
            if parameter.kind == "path":
                # Any path variable is required
                assert parameter.required
                required_string = "required in path"

            if parameter.required:
                required_block = f'<span class="api-argument-required">{required_string}</span>'
            else:
                required_block = '<span class="api-argument-optional">optional</span>'

            check_deprecated_consistency(parameter.deprecated, description)
            if parameter.deprecated:
                deprecated_block = '<span class="api-argument-deprecated">Deprecated</span>'
            else:
                deprecated_block = ""

            object_block = ""
            # TODO: There are some endpoint parameters with object properties
            # that are not defined in `zerver/openapi/zulip.yaml`
            if "object" in data_type:
                object_schema = parameter.value_schema

                if "items" in object_schema and "properties" in object_schema["items"]:
                    object_block = self.render_object_details(object_schema["items"], str(name))
                elif "properties" in object_schema:
                    object_block = self.render_object_details(object_schema, str(name))
                elif "oneOf" in object_schema:
                    object_block = self.render_oneof_block(object_schema, str(name))

            lines.append(
                API_PARAMETER_TEMPLATE.format(
                    argument=name,
                    example=escape_html(example),
                    required=required_block,
                    deprecated=deprecated_block,
                    description=md_engine.convert(description),
                    type=data_type,
                    object_details=object_block,
                )
            )

        return lines

    def render_object_details(
        self, schema: Mapping[str, Any], name: str, oneof: bool = False
    ) -> str:
        md_engine = markdown.Markdown(extensions=[])
        li_elements = []

        object_values = schema.get("properties", {})
        for value in object_values:
            description = ""
            if "description" in object_values[value]:
                description = object_values[value]["description"]

            # check for default, enum, required or example in documentation
            additions: list[str] = []

            default = object_values.get(value, {}).get("default")
            if default is not None:
                formatted_default = OBJECT_CODE_TEMPLATE.format(value=json.dumps(default))
                additions += f"Defaults to {formatted_default}. "

            enums = object_values.get(value, {}).get("enum")
            if enums is not None:
                formatted_enums = [
                    OBJECT_CODE_TEMPLATE.format(value=json.dumps(enum)) for enum in enums
                ]
                additions += "Must be one of: {}. ".format(", ".join(formatted_enums))

            if "example" in object_values[value]:
                example = json.dumps(object_values[value]["example"])
                formatted_example = OBJECT_CODE_TEMPLATE.format(value=escape_html(example))
                additions += (
                    f'<span class="api-argument-example-label">Example</span>: {formatted_example}'
                )

            if len(additions) > 0:
                additional_information = "".join(additions).strip()
                description_final = OBJECT_DESCRIPTION_TEMPLATE.format(
                    description=md_engine.convert(description),
                    additional_information=additional_information,
                )
            else:
                description_final = md_engine.convert(description)

            required_block = ""
            if "required" in schema:
                if value in schema["required"]:
                    required_block = '<span class="api-argument-required">required</span>'
                else:
                    required_block = '<span class="api-argument-optional">optional</span>'

            data_type = generate_data_type(object_values[value])

            details = ""
            if "object" in data_type and "properties" in object_values[value]:
                details += self.render_object_details(object_values[value], str(value))
            elif "oneOf" in object_values[value]:
                details += self.render_oneof_block(object_values[value], str(value))

            li = OBJECT_LIST_ITEM_TEMPLATE.format(
                value=value,
                data_type=data_type,
                required=required_block,
                description=description_final,
                object_details=details,
            )

            li_elements.append(li)
        if oneof:
            object_details = ONEOF_OBJECT_DETAILS_TEMPLATE.format(
                values="\n".join(li_elements),
            )
        else:
            object_details = OBJECT_DETAILS_TEMPLATE.format(
                argument=name,
                values="\n".join(li_elements),
            )
        return object_details


def makeExtension(*args: Any, **kwargs: str) -> MarkdownArgumentsTableGenerator:
    return MarkdownArgumentsTableGenerator(*args, **kwargs)


def generate_data_type(schema: Mapping[str, Any]) -> str:
    data_type = ""
    if "oneOf" in schema:
        data_type = " | ".join(generate_data_type(item) for item in schema["oneOf"])
    elif "items" in schema:
        data_type = "(" + generate_data_type(schema["items"]) + ")[]"
    else:
        data_type = schema["type"]
        if schema.get("nullable", False):
            data_type += " | null"
    return data_type
