import ClipboardJS from "clipboard";
import $ from "jquery";
import type * as tippy from "tippy.js";
import * as z from "zod/mini";

import render_generate_integration_url_config_checkbox_modal from "../templates/settings/generate_integration_url_config_checkbox_modal.hbs";
import render_generate_integration_url_config_text_modal from "../templates/settings/generate_integration_url_config_text_modal.hbs";
import render_generate_integration_url_filter_branches_modal from "../templates/settings/generate_integration_url_filter_branches_modal.hbs";
import render_generate_integration_url_modal from "../templates/settings/generate_integration_url_modal.hbs";
import render_integration_events from "../templates/settings/integration_events.hbs";

import {show_copied_confirmation} from "./copied_tooltip.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import type {DropdownWidget, Option} from "./dropdown_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import * as branch_pill from "./integration_branch_pill.ts";
import {realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as util from "./util.ts";

type UrlOption = {
    key: string;
    label: string;
    validator: string;
};

type TopicUIParams = {
    // The topic configuration inputs are:
    // override_topic and Slack-specific slack_topics_dropdown_widget
    disable_topic_config_inputs: boolean;
    show_topic_input?: boolean;
};

const url_option_schema = z.object({
    key: z.string(),
    label: z.string(),
    validator: z.string(),
});

const url_options_schema = z.array(url_option_schema);

const PresetUrlOption = {
    BRANCHES: "branches",
    CHANNEL_MAPPING: "mapping",
};

export function show_generate_integration_url_modal(api_key: string): void {
    const default_url_message = $t_html({defaultMessage: "Integration URL will appear here."});
    const streams = stream_data.subscribed_subs();
    const direct_messages_option = {
        name: $t_html({defaultMessage: "Direct message to me"}),
        unique_id: -1,
        is_direct_message: true,
    };
    const map_channels_option: Option = {
        name: $t_html({defaultMessage: "Matching Zulip channel"}),
        unique_id: -2,
    };
    const html_body = render_generate_integration_url_modal({
        default_url_message,
        max_topic_length: realm.max_topic_length,
    });

    const topics_named_after_slack_channels_option: Option = {
        name: $t_html({defaultMessage: "Topics named after Slack channels"}),
        unique_id: "map_topics_to_slack_channels",
    };

    const send_all_to_single_topic_option: Option = {
        name: $t_html({defaultMessage: "Send all notifications to a single topic"}),
        unique_id: "send_all_to_a_topic",
    };

    function generate_integration_url_post_render(): void {
        let selected_integration: string | undefined;
        let stream_input_dropdown_widget: DropdownWidget;
        let integration_input_dropdown_widget: DropdownWidget;
        let slack_topics_dropdown_widget: DropdownWidget;
        let previous_selected_integration: string | undefined;
        let branch_pill_widget: branch_pill.BranchPillWidget | undefined;

        const slack_topics_dropdown_widget_id = "slack-topics-dropdown";
        const $override_topic = $<HTMLInputElement>("input#integration-url-override-topic");
        const $topic_input = $<HTMLInputElement>("input#integration-url-topic-input");
        const $integration_url = $("#generate-integration-url-modal .integration-url");
        const $dialog_submit_button = $("#generate-integration-url-modal .dialog_submit_button");
        const $show_integration_events = $("#show-integration-events");
        const $config_container = $("#integration-url-config-options-container");
        const $slack_topics_dropdown = $(`#${slack_topics_dropdown_widget_id}_widget`);

        $dialog_submit_button.prop("disabled", true);
        $("#integration-url-stream_widget").prop("disabled", true);

        const clipboard = new ClipboardJS("#generate-integration-url-modal .dialog_submit_button", {
            text() {
                return $integration_url.text();
            },
        });
        clipboard.on("success", () => {
            show_copied_confirmation(
                util.the($("#generate-integration-url-modal .dialog_submit_button")),
            );
        });

        function show_branch_filtering_ui(): void {
            $("#integration-url-filter-branches").toggleClass(
                "hide",
                $("#integration-url-all-branches").prop("checked"),
            );

            const $pill_container = $("#integration-url-filter-branches .pill-container");
            if ($pill_container.length > 0 && branch_pill_widget === undefined) {
                branch_pill_widget = branch_pill.create_pills($pill_container);
                branch_pill_widget.onPillCreate(() => {
                    update_url();
                });
                branch_pill_widget.onPillRemove(() => {
                    update_url();
                });
            }

            if (
                !$("#integration-url-all-branches").prop("checked") &&
                branch_pill_widget?.items().length === 0
            ) {
                branch_pill_widget.appendValue("main");
            }

            $("#integration-url-branches-text").trigger("focus");
            update_url();
        }

        function set_input_disabled_state($input: JQuery, disable: boolean): void {
            $input
                .prop("disabled", disable)
                .closest(".input-group")
                .toggleClass("control-label-disabled", disable);
        }

        function update_topic_ui({
            disable_topic_config_inputs,
            show_topic_input,
        }: TopicUIParams): void {
            set_input_disabled_state($override_topic, disable_topic_config_inputs);
            set_input_disabled_state($slack_topics_dropdown, disable_topic_config_inputs);

            if (show_topic_input === undefined) {
                return;
            }

            $override_topic.prop("checked", show_topic_input);
            slack_topics_dropdown_widget.render(
                show_topic_input ? send_all_to_single_topic_option.unique_id : "",
            );
        }

        function render_url_options(config: UrlOption[]): void {
            const validated_config = url_options_schema.parse(config);
            $config_container.empty();

            for (const option of validated_config) {
                let $config_element: JQuery;

                if (option.key === PresetUrlOption.BRANCHES) {
                    const filter_branches_html =
                        render_generate_integration_url_filter_branches_modal();
                    $config_element = $(filter_branches_html);
                    $config_element.find("#integration-url-all-branches").on("change", () => {
                        show_branch_filtering_ui();
                    });
                } else if (option.key === PresetUrlOption.CHANNEL_MAPPING) {
                    continue;
                } else if (option.validator === "check_bool") {
                    const config_html = render_generate_integration_url_config_checkbox_modal({
                        key: option.key,
                        label: option.label,
                    });
                    $config_element = $(config_html);
                    $config_element
                        .find(`#integration-url-${option.key}-checkbox`)
                        .on("change", () => {
                            update_url();
                        });
                } else if (option.validator === "check_string") {
                    const config_html = render_generate_integration_url_config_text_modal({
                        key: option.key,
                        label: option.label,
                    });
                    $config_element = $(config_html);
                    $config_element.find(`#integration-url-${option.key}-text`).on("input", () => {
                        update_url();
                    });
                } else {
                    continue;
                }
                $config_container.append($config_element);
            }
        }

        function topic_ui_callback(show_topic_text_field: boolean): void {
            $topic_input.parent().toggleClass("hide", !show_topic_text_field);
            if (!$topic_input.parent().hasClass("hide")) {
                $topic_input.trigger("focus");
            }
        }

        $override_topic.on("change", function () {
            const checked = this.checked;
            topic_ui_callback(checked);
        });

        $show_integration_events.on("change", () => {
            $("#integrations-event-container").toggleClass(
                "hide",
                !$show_integration_events.prop("checked"),
            );
            update_url(true);
        });

        $(document).on("change", "#integrations-event-container .integration-event", () => {
            update_url();
        });

        $("#add-all-integration-events").on("click", () => {
            $("#integrations-event-container .integration-event").prop("checked", true);
            update_url();
        });

        $("#remove-all-integration-events").on("click", () => {
            $("#integrations-event-container .integration-event").prop("checked", false);
            update_url();
        });

        $("#generate-integration-url-modal .integration-url-parameter").on("change input", () => {
            update_url();
        });

        function update_url(render_events = false): void {
            selected_integration = integration_input_dropdown_widget.value()!.toString();
            if (previous_selected_integration !== selected_integration) {
                reset_to_blank_state();
            }
            $("#integration-url-stream_widget").prop("disabled", false);
            previous_selected_integration = selected_integration;

            const stream_id = stream_input_dropdown_widget.value();
            const topic_name = $topic_input.val()!;

            const selected_integration_data = realm.realm_incoming_webhook_bots.find(
                (bot) => bot.name === selected_integration,
            );
            const all_event_types = selected_integration_data?.all_event_types;
            const url_options = selected_integration_data?.url_options;

            if (all_event_types !== null) {
                $("#integration-events-parameter").removeClass("hide");
            }

            if ($show_integration_events.prop("checked") && render_events) {
                const events_with_ids = all_event_types?.map((event) => {
                    const event_id = event.replaceAll(/\s+/g, "-");
                    return {
                        event,
                        event_id,
                    };
                });
                events_with_ids?.sort((a, b) => a.event.localeCompare(b.event));
                const events_html = render_integration_events({
                    events: events_with_ids,
                });
                $("#integrations-event-options").html(events_html);
            }

            const params = new URLSearchParams({api_key});
            if (stream_id !== -1) {
                params.set("stream", stream_id!.toString());

                // These are Slack-specific settings.
                if (selected_integration === "slack") {
                    // This replaces the $override_topic field.
                    const selected_slack_topic_option = slack_topics_dropdown_widget.value();
                    if (
                        selected_slack_topic_option ===
                        topics_named_after_slack_channels_option.unique_id
                    ) {
                        params.set("channels_map_to_topics", "1");
                    } else if (
                        selected_slack_topic_option === send_all_to_single_topic_option.unique_id &&
                        topic_name !== ""
                    ) {
                        params.delete("channels_map_to_topics");
                        params.set("topic", topic_name);
                    }
                } else {
                    if ($override_topic.prop("checked") && topic_name !== "") {
                        params.set("topic", topic_name);
                    }
                }
            }

            const selected_events = set_events_param(params);

            if (url_options) {
                for (const option of url_options) {
                    let $input_element;
                    if (option.key === PresetUrlOption.CHANNEL_MAPPING) {
                        const stream_input = stream_input_dropdown_widget.value();
                        if (stream_input === map_channels_option?.unique_id) {
                            params.delete("stream");
                            params.set(PresetUrlOption.CHANNEL_MAPPING, "channels");
                        }
                    } else if (option.key === PresetUrlOption.BRANCHES) {
                        if ($("#integration-url-all-branches").prop("checked")) {
                            continue;
                        }
                        const $pill_container = $(
                            "#integration-url-filter-branches .pill-container",
                        );
                        if ($pill_container.length > 0 && branch_pill_widget !== undefined) {
                            const branch_names = branch_pill_widget
                                .items()
                                .map((item) => item.branch)
                                .join(",");
                            if (branch_names !== "") {
                                params.set(option.key, branch_names);
                            }
                        }
                    } else if (option.validator === "check_bool") {
                        $input_element = $(`#integration-url-${option.key}-checkbox`);
                        if ($input_element.prop("checked")) {
                            params.set(option.key, "true");
                        }
                    } else if (option.validator === "check_string") {
                        $input_element = $(`#integration-url-${option.key}-text`);
                        const value = $input_element.val();
                        if (value) {
                            params.set(option.key, value.toString());
                        }
                    }
                }
            }

            const realm_url = realm.realm_url;
            const base_url = `${realm_url}/api/v1/external/`;
            $integration_url.text(`${base_url}${selected_integration}?${params.toString()}`);
            $dialog_submit_button.prop("disabled", false);

            if (
                ($override_topic.prop("checked") && topic_name === "") ||
                ($show_integration_events.prop("checked") && !selected_events)
            ) {
                $dialog_submit_button.prop("disabled", true);
            }
        }

        integration_input_dropdown_widget = new dropdown_widget.DropdownWidget({
            widget_name: "integration-name",
            get_options: get_options_for_integration_input_dropdown_widget,
            item_click_callback: integration_item_click_callback,
            $events_container: $("#generate-integration-url-modal"),
            default_id: "",
            text_if_current_value_not_in_options: $t_html({
                defaultMessage: "Select an integration",
            }),
            unique_id_type: "string",
        });
        integration_input_dropdown_widget.setup();

        function get_options_for_integration_input_dropdown_widget(): Option[] {
            const options = realm.realm_incoming_webhook_bots
                .toSorted((a, b) => util.strcmp(a.display_name, b.display_name))
                .map((bot) => ({
                    name: bot.display_name,
                    unique_id: bot.name,
                }));
            return options;
        }

        function integration_item_click_callback(
            event: JQuery.ClickEvent,
            dropdown: tippy.Instance,
        ): void {
            integration_input_dropdown_widget.render();
            $(".integration-url-name-wrapper").trigger("input");

            const selected_integration = integration_input_dropdown_widget.value();
            const selected_integration_data = realm.realm_incoming_webhook_bots.find(
                (bot) => bot.name === selected_integration,
            );
            const url_options = selected_integration_data?.url_options;

            if (url_options) {
                render_url_options(url_options);
            }

            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
        }

        stream_input_dropdown_widget = new dropdown_widget.DropdownWidget({
            widget_name: "integration-url-stream",
            get_options: get_options_for_stream_dropdown_widget,
            item_click_callback: stream_item_click_callback,
            $events_container: $("#generate-integration-url-modal"),
            default_id: direct_messages_option.unique_id,
            unique_id_type: "number",
        });
        stream_input_dropdown_widget.setup();

        $slack_topics_dropdown.closest(".input-group").hide();
        slack_topics_dropdown_widget = new dropdown_widget.DropdownWidget({
            widget_name: slack_topics_dropdown_widget_id,
            get_options() {
                return [topics_named_after_slack_channels_option, send_all_to_single_topic_option];
            },
            item_click_callback: slack_topics_click_callback,
            $events_container: $("#generate-integration-url-modal"),
            text_if_current_value_not_in_options: $t({
                defaultMessage: "Select notification topics",
            }),
            unique_id_type: "string",
            default_id: "",
        });
        slack_topics_dropdown_widget.setup();

        function slack_topics_click_callback(
            event: JQuery.ClickEvent,
            dropdown: tippy.Instance,
            widget: DropdownWidget,
        ): void {
            slack_topics_dropdown_widget.render();
            topic_ui_callback(widget.value() === send_all_to_single_topic_option.unique_id);
            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
        }

        function get_additional_stream_dropdown_options(): Option[] {
            const additional_options: Option[] = [];

            const selected_integration = integration_input_dropdown_widget.value();
            const selected_integration_data = realm.realm_incoming_webhook_bots.find(
                (bot) => bot.name === selected_integration,
            );
            if (!selected_integration) {
                return additional_options;
            }

            const url_options = selected_integration_data?.url_options;
            if (!url_options) {
                return additional_options;
            }

            const mapping_option = url_options?.find(
                (option) => option.key === PresetUrlOption.CHANNEL_MAPPING,
            );

            if (mapping_option) {
                additional_options.push(map_channels_option);
            }
            return additional_options;
        }

        function get_options_for_stream_dropdown_widget(): Option[] {
            const additional_options = get_additional_stream_dropdown_options();
            const options = [
                direct_messages_option,
                ...additional_options,
                ...streams
                    .filter((stream) => stream_data.can_post_messages_in_stream(stream))
                    .map((stream) => ({
                        name: stream.name,
                        unique_id: stream.stream_id,
                        stream,
                    })),
            ];
            return options;
        }

        function stream_item_click_callback(
            event: JQuery.ClickEvent,
            dropdown: tippy.Instance,
        ): void {
            stream_input_dropdown_widget.render();
            $(".integration-url-stream-wrapper").trigger("input");
            dropdown.hide();
            const user_selected_option = stream_input_dropdown_widget.value();
            if (user_selected_option === direct_messages_option.unique_id) {
                update_topic_ui({
                    disable_topic_config_inputs: true,
                    show_topic_input: false,
                });
                $topic_input.val("");
            } else if (user_selected_option === map_channels_option.unique_id) {
                update_topic_ui({
                    disable_topic_config_inputs: true,
                    show_topic_input: true,
                });
                $topic_input.val("");
                $topic_input.parent().removeClass("hide");
            } else {
                update_topic_ui({
                    disable_topic_config_inputs: false,
                });
            }

            if (selected_integration === "slack") {
                topic_ui_callback(
                    slack_topics_dropdown_widget.value() ===
                        send_all_to_single_topic_option.unique_id,
                );
            } else {
                $override_topic.trigger("change");
            }
            event.preventDefault();
            event.stopPropagation();
        }

        function set_events_param(params: URLSearchParams): boolean {
            if (!$show_integration_events.prop("checked")) {
                return false;
            }
            const $selected_integration_events = $(
                "#integrations-event-container .integration-event:checked",
            );

            const selected_events = $selected_integration_events
                .map(function () {
                    return $(this).val();
                })
                .get();
            if (selected_events.length > 0) {
                params.set("only_events", JSON.stringify(selected_events));
                return true;
            }
            return false;
        }

        function reset_to_blank_state(): void {
            $("#integration-events-parameter").addClass("hide");
            $("#integrations-event-container").addClass("hide");
            $("#integrations-event-options").empty();
            $("#integrations-event-container .integration-event").prop("checked", false);
            $show_integration_events.prop("checked", false);
            if (selected_integration === "slack") {
                $override_topic.closest(".input-group").hide();
                $slack_topics_dropdown.closest(".input-group").show();
            } else {
                $override_topic.closest(".input-group").show();
                $slack_topics_dropdown.closest(".input-group").hide();
            }
            update_topic_ui({
                disable_topic_config_inputs: true,
                show_topic_input: false,
            });
            $topic_input.val("");
            $topic_input.parent().addClass("hide");

            stream_input_dropdown_widget.render(direct_messages_option.unique_id);
            $config_container.empty();
            branch_pill_widget = undefined;
        }
    }

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Generate URL for an integration"}),
        html_body,
        id: "generate-integration-url-modal",
        html_submit_button: $t_html({defaultMessage: "Copy URL"}),
        html_exit_button: $t_html({defaultMessage: "Close"}),
        on_click() {
            return;
        },
        post_render: generate_integration_url_post_render,
        on_shown() {
            $("#integration-name_widget").trigger("focus");
        },
    });
}
