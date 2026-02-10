import copy
import json
import re
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from typing_extensions import override

from zerver.lib.markdown.priorities import PREPROCESSOR_PRIORITIES
from zerver.openapi.openapi import check_deprecated_consistency, get_openapi_return_values

from .api_arguments_table_generator import generate_data_type

REGEXP = re.compile(r"\{generate_return_values_table\|\s*(.+?)\s*\|\s*(.+)\s*\}")

EVENT_HEADER_TEMPLATE = """
<div class="api-event-header">
    <h3 id="{id}"><span class="api-event-name">{event}</span></h3>
</div>
""".strip()

OP_TEMPLATE = '<span class="api-event-op">op: {op_type}</span>'

EVENTS_TABLE_TEMPLATE = """
<div class="api-events-table">
{events_list}
</div>
<hr>
""".strip()

TABLE_OPS_TEMPLATE = """
<div class="api-event-type">{event_name}:</div>
<div class="api-event-ops">
{ops}
</div>
""".strip()

TABLE_LINK_TEMPLATE = """
<div class="api-event-link">
    <a href="#{url}">{link_name}</a>
</div>
""".strip()


@dataclass
class EventData:
    type: str
    description: str
    properties: dict[str, Any]
    example: str
    op_type: str | None = None


class MarkdownReturnValuesTableGenerator(Extension):
    @override
    def extendMarkdown(self, md: markdown.Markdown) -> None:
        md.preprocessors.register(
            APIReturnValuesTablePreprocessor(md, self.getConfigs()),
            "generate_return_values",
            PREPROCESSOR_PRIORITIES["generate_return_values"],
        )


class APIReturnValuesTablePreprocessor(Preprocessor):
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
                return_values = get_openapi_return_values(endpoint, method)
                if doc_name == "/events:get":
                    return_values = copy.deepcopy(return_values)
                    events = return_values["events"].pop("items", None)
                    text = self.render_table(return_values, 0)
                    # Another heading for the events documentation
                    text.append("\n\n## Events by `type`\n\n")
                    text += self.render_events(events)
                else:
                    text = self.render_table(return_values, 0)
                if len(text) > 0:
                    text = ["#### Return values", *text]
                line_split = REGEXP.split(line, maxsplit=0)
                preceding = line_split[0]
                following = line_split[-1]
                text = [preceding, *text, following]
                lines = lines[:loc] + text + lines[loc + 1 :]
                break
            else:
                done = True
        return lines

    def render_desc(
        self, description: str, spacing: int, data_type: str, return_value: str | None = None
    ) -> str:
        description = description.replace("\n", "\n" + ((spacing + 4) * " "))
        if return_value is None:
            # HACK: It's not clear how to use OpenAPI data to identify
            # the `key` fields for objects where e.g. the keys are
            # user/stream IDs being mapped to data associated with
            # those IDs.  We hackily describe those fields by
            # requiring that the descriptions be written as `key_name:
            # key_description` and parsing for that pattern; we need
            # to be careful to skip cases where we'd have `Note: ...`
            # on a later line.
            #
            # More correctly, we should be doing something that looks at the types;
            # print statements and test_api_doc_endpoint is useful for testing.
            arr = description.split(": ", 1)
            if len(arr) == 1 or "\n" in arr[0]:
                return (spacing * " ") + "* " + description
            (key_name, key_description) = arr
            return (
                (spacing * " ")
                + "* "
                + key_name
                + ": "
                + '<span class="api-field-type">'
                + data_type
                + "</span>\n\n"
                + (spacing + 4) * " "
                + key_description
            )
        return (
            (spacing * " ")
            + "* `"
            + return_value
            + "`: "
            + '<span class="api-field-type">'
            + data_type
            + "</span>\n\n"
            + (spacing + 4) * " "
            + description
        )

    def render_oneof_block(self, object_schema: dict[str, Any], spacing: int) -> list[str]:
        ans = []
        block_spacing = spacing
        for element in object_schema["oneOf"]:
            spacing = block_spacing
            if "description" not in element:
                # If the description is not present, we still need to render the rest
                # of the documentation of the element shifted towards left of the page.
                spacing -= 4
            else:
                # Add the specialized description of the oneOf element.
                data_type = generate_data_type(element)
                ans.append(self.render_desc(element["description"], spacing, data_type))
            # If the oneOf element is an object schema then render the documentation
            # of its keys.
            if "properties" in element:
                ans += self.render_table(element["properties"], spacing + 4)

            if "items" in element:
                if "properties" in element["items"]:
                    ans += self.render_table(element["items"]["properties"], spacing + 4)
                elif "oneOf" in element["items"]:  #  nocoverage
                    # This block is for completeness.
                    ans += self.render_oneof_block(element["items"], spacing + 4)

            if element.get("additionalProperties", False):
                additional_properties = element["additionalProperties"]
                if "description" in additional_properties:
                    data_type = generate_data_type(additional_properties)
                    ans.append(
                        self.render_desc(
                            additional_properties["description"], spacing + 4, data_type
                        )
                    )
                if "properties" in additional_properties:
                    ans += self.render_table(
                        additional_properties["properties"],
                        spacing + 8,
                    )
        return ans

    def render_table(self, return_values: dict[str, Any], spacing: int) -> list[str]:
        IGNORE = ["result", "msg", "ignored_parameters_unsupported"]
        ans = []
        for return_value, schema in return_values.items():
            if return_value in IGNORE:
                continue
            if "oneOf" in schema:
                # For elements using oneOf there are two descriptions. The first description
                # should be at level with the oneOf and should contain the basic non-specific
                # description of the endpoint. Then for each element of oneOf there is a
                # specialized description for that particular case. The description used
                # right below is the main description.
                data_type = generate_data_type(schema)
                ans.append(
                    self.render_desc(schema["description"], spacing, data_type, return_value)
                )
                ans += self.render_oneof_block(schema, spacing + 4)
                continue
            description = schema["description"]
            data_type = generate_data_type(schema)
            check_deprecated_consistency(schema.get("deprecated", False), description)
            ans.append(self.render_desc(description, spacing, data_type, return_value))
            if "properties" in schema:
                ans += self.render_table(schema["properties"], spacing + 4)
            if schema.get("additionalProperties", False):
                data_type = generate_data_type(schema["additionalProperties"])
                ans.append(
                    self.render_desc(
                        schema["additionalProperties"]["description"],
                        spacing + 4,
                        data_type,
                    )
                )
                if "properties" in schema["additionalProperties"]:
                    ans += self.render_table(
                        schema["additionalProperties"]["properties"],
                        spacing + 8,
                    )
                elif "oneOf" in schema["additionalProperties"]:
                    ans += self.render_oneof_block(schema["additionalProperties"], spacing + 8)
                elif schema["additionalProperties"].get("additionalProperties", False):
                    data_type = generate_data_type(
                        schema["additionalProperties"]["additionalProperties"]
                    )
                    ans.append(
                        self.render_desc(
                            schema["additionalProperties"]["additionalProperties"]["description"],
                            spacing + 8,
                            data_type,
                        )
                    )

                    ans += self.render_table(
                        schema["additionalProperties"]["additionalProperties"]["properties"],
                        spacing + 12,
                    )
            if "items" in schema:
                if "properties" in schema["items"]:
                    ans += self.render_table(schema["items"]["properties"], spacing + 4)
                elif "oneOf" in schema["items"]:
                    ans += self.render_oneof_block(schema["items"], spacing + 4)
        return ans

    def generate_event_strings(self, event_data: EventData) -> list[str]:
        event_strings: list[str] = []
        if event_data.op_type is None:
            event_strings.append(
                EVENT_HEADER_TEMPLATE.format(id=event_data.type, event=event_data.type)
            )
        else:
            op_detail = OP_TEMPLATE.format(op_type=event_data.op_type)
            event_strings.append(
                EVENT_HEADER_TEMPLATE.format(
                    id=f"{event_data.type}-{event_data.op_type}",
                    event=f"{event_data.type} {op_detail}",
                )
            )
        event_strings.append(f"\n{event_data.description}\n\n\n")
        event_strings += self.render_table(event_data.properties, 0)
        event_strings.append("**Example**")
        event_strings.append("\n```json\n")
        event_strings.append(event_data.example)
        event_strings.append("```\n\n")
        event_strings.append("<hr>")
        return event_strings

    def generate_events_table(self, events_by_type: OrderedDict[str, list[str]]) -> list[str]:
        event_links: list[str] = []
        for event_type, event_ops in events_by_type.items():
            if not event_ops:
                event_links.append(TABLE_LINK_TEMPLATE.format(link_name=event_type, url=event_type))
            else:
                event_ops.sort()
                ops_list = [
                    TABLE_LINK_TEMPLATE.format(link_name=f"op: {op}", url=f"{event_type}-{op}")
                    for op in event_ops
                ]
                event_links.append(
                    TABLE_OPS_TEMPLATE.format(event_name=event_type, ops="\n".join(ops_list))
                )
        return [EVENTS_TABLE_TEMPLATE.format(events_list="\n".join(event_links))]

    def render_events(self, events_dict: dict[str, Any]) -> list[str]:
        events: list[str] = []
        events_for_table: OrderedDict[str, list[str]] = OrderedDict()
        for event in events_dict["oneOf"]:
            # The op property doesn't have a description, so it must be removed
            # before any calls to self.render_table, which expects a description.
            op: dict[str, Any] | None = event["properties"].pop("op", None)
            op_type: str | None = None
            if op is not None:
                op_type = op["enum"][0]
            event_data = EventData(
                type=event["properties"]["type"]["enum"][0],
                description=event["description"],
                properties=event["properties"],
                example=json.dumps(event["example"], indent=4, sort_keys=True),
                op_type=op_type,
            )
            events += self.generate_event_strings(event_data)
            if event_data.op_type is None:
                events_for_table[event_data.type] = []
            elif event_data.type in events_for_table:
                events_for_table[event_data.type] += [event_data.op_type]
            else:
                events_for_table[event_data.type] = [event_data.op_type]
        events_table = self.generate_events_table(OrderedDict(sorted(events_for_table.items())))
        return events_table + events


def makeExtension(*args: Any, **kwargs: str) -> MarkdownReturnValuesTableGenerator:
    return MarkdownReturnValuesTableGenerator(*args, **kwargs)
