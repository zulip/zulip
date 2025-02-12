import ClipboardJS from "clipboard";
import $ from "jquery";
import type * as tippy from "tippy.js";
import type {z} from "zod";

import render_generate_integration_url_config_checkbox_modal from "../templates/settings/generate_integration_url_config_checkbox_modal.hbs";
import render_generate_integration_url_config_text_modal from "../templates/settings/generate_integration_url_config_text_modal.hbs";
import render_generate_integration_url_filter_branches_modal from "../templates/settings/generate_integration_url_filter_branches_modal.hbs";
import render_generate_integration_url_modal from "../templates/settings/generate_integration_url_modal.hbs";
import render_integration_events from "../templates/settings/integration_events.hbs";

import {show_copied_confirmation} from "./copied_tooltip.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import type {DropdownWidget, Option} from "./dropdown_widget.ts";
import {$t_html} from "./i18n.ts";
import type {
    integration_config_option_schema,
    integrations_interfaced_settings_schema,
} from "./state_data.ts";
import {realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import {place_caret_at_end} from "./ui_util.ts";
import * as util from "./util.ts";

type ConfigOption = z.infer<typeof integration_config_option_schema>;

type EventType = string;

type InterfacedSetting = z.infer<typeof integrations_interfaced_settings_schema>;

class IntegrationData {
    selected_integration: string;
    config_options: ConfigOption[] | undefined = undefined;
    all_event_types: EventType[] | null = null;
    interfaced_settings: InterfacedSetting | undefined = undefined;
    integration_logo_url = "";

    constructor(selected_integration: string) {
        const selected_integration_data = realm.realm_incoming_webhook_bots.find(
            (bot) => bot.name === selected_integration,
        );
        this.selected_integration = selected_integration;
        this.config_options = selected_integration_data?.config_options;
        if (selected_integration_data?.all_event_types) {
            this.all_event_types = selected_integration_data.all_event_types;
        }
        if (selected_integration_data?.interfaced_settings) {
            this.interfaced_settings = selected_integration_data.interfaced_settings;
        }
        if (selected_integration_data) {
            this.integration_logo_url = `/static/images/integrations/logos/${selected_integration}.svg`;
        }
    }
}

export function show_generate_integration_url_modal(api_key: string): void {
    const default_url_message = $t_html({defaultMessage: "Integration URL will appear here."});
    const streams = stream_data.subscribed_subs();
    const default_integration_option = {
        name: $t_html({defaultMessage: "Select an integration"}),
        unique_id: "",
    };
    const direct_messages_option = {
        name: $t_html({defaultMessage: "Direct message to me"}),
        unique_id: -1,
        is_direct_message: true,
    };
    const map_to_channels_option = {
        name: $t_html({defaultMessage: "Map to Zulip channels"}),
        unique_id: -2,
        integration_logo_url: "",
        is_interfaced_setting: true,
    };
    const html_body = render_generate_integration_url_modal({
        default_url_message,
        max_topic_length: realm.max_topic_length,
    });
    let selected_integration_data: IntegrationData;

    function generate_integration_url_post_render(): void {
        let selected_integration = "";
        let stream_input_dropdown_widget: DropdownWidget;
        let integration_input_dropdown_widget: DropdownWidget;
        let previous_selected_integration = "";

        const $override_topic = $<HTMLInputElement>("input#integration-url-override-topic");
        const $topic_input = $<HTMLInputElement>("input#integration-url-topic-input");
        const $integration_url = $("#generate-integration-url-modal .integration-url");
        const $dialog_submit_button = $("#generate-integration-url-modal .dialog_submit_button");
        const $show_integration_events = $("#show-integration-events");
        const $config_container = $("#integration-url-config-options-container");

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

        function render_config(config: ConfigOption[]): void {
            $config_container.empty();

            for (const option of config) {
                let $config_element: JQuery;

                if (option.key === "branches") {
                    const filter_branches_html =
                        render_generate_integration_url_filter_branches_modal();
                    $config_element = $(filter_branches_html);
                    $config_element.find("#integration-url-all-branches").on("change", () => {
                        $("#integration-url-filter-branches").toggleClass(
                            "hide",
                            $("#integration-url-all-branches").prop("checked"),
                        );
                        $("#integration-url-branches-text").trigger("focus");
                        place_caret_at_end(util.the($("#integration-url-branches-text")));
                        update_url();
                    });
                    $config_element.find("#integration-url-branches-text").on("input", () => {
                        update_url();
                    });
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

        $override_topic.on("change", function () {
            const checked = this.checked;
            $topic_input.parent().toggleClass("hide", !checked);
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
            if (selected_integration === default_integration_option.unique_id) {
                $("#integration-url-stream_widget").prop("disabled", true);
                $integration_url.text(default_url_message);
                $dialog_submit_button.prop("disabled", true);
                return;
            }
            $("#integration-url-stream_widget").prop("disabled", false);
            previous_selected_integration = selected_integration;

            const stream_id = stream_input_dropdown_widget.value();
            const topic_name = $topic_input.val()!;

            selected_integration_data = new IntegrationData(selected_integration);

            const all_event_types = selected_integration_data?.all_event_types;
            const config = selected_integration_data?.config_options;

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
            const interfaced_settings = selected_integration_data?.interfaced_settings;
            const map_to_channel_setting = interfaced_settings?.MapToChannelsT;

            if (map_to_channel_setting && stream_id === map_to_channel_setting.unique_query) {
                params.set(map_to_channel_setting.unique_query, "true");
            } else if (stream_id !== -1) {
                params.set("stream", stream_id!.toString());
                if ($override_topic.prop("checked") && topic_name !== "") {
                    params.set("topic", topic_name);
                }
            }

            const selected_events = set_events_param(params);

            if (config) {
                for (const option of config) {
                    let $input_element;
                    if (option.validator === "check_bool") {
                        $input_element = $(`#integration-url-${option.key}-checkbox`);
                        if ($input_element.prop("checked")) {
                            params.set(option.key, "true");
                        }
                    } else if (option.validator === "check_string") {
                        $input_element = $(`#integration-url-${option.key}-text`);
                        const value = $input_element.val();
                        // If the config option is "branches", ensure the checkbox is unchecked.
                        if (
                            value &&
                            (option.key !== "branches" ||
                                $<HTMLInputElement>("#integration-url-all-branches").prop(
                                    "checked",
                                ) === false)
                        ) {
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
            default_id: default_integration_option.unique_id,
            unique_id_type: dropdown_widget.DataTypes.STRING,
        });
        integration_input_dropdown_widget.setup();

        function get_options_for_integration_input_dropdown_widget(): Option[] {
            const options = [
                default_integration_option,
                ...realm.realm_incoming_webhook_bots
                    .sort((a, b) => util.strcmp(a.display_name, b.display_name))
                    .map((bot) => ({
                        name: bot.display_name,
                        unique_id: bot.name,
                    })),
            ];
            return options;
        }

        function integration_item_click_callback(
            event: JQuery.ClickEvent,
            dropdown: tippy.Instance,
        ): void {
            integration_input_dropdown_widget.render();
            $(".integration-url-name-wrapper").trigger("input");

            if (selected_integration_data?.config_options) {
                render_config(selected_integration_data.config_options);
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
            unique_id_type: dropdown_widget.DataTypes.NUMBER,
        });
        stream_input_dropdown_widget.setup();

        function get_additional_stream_dropdown_options(): Option[] {
            const map_to_channel_setting =
                selected_integration_data?.interfaced_settings?.MapToChannelsT;
            const additional_options: Option[] = [];
            if (map_to_channel_setting) {
                map_to_channels_option.integration_logo_url =
                    selected_integration_data.integration_logo_url;
                additional_options.push(map_to_channels_option);
            }
            return additional_options;
        }

        function get_options_for_stream_dropdown_widget(): Option[] {
            const additional_settings = get_additional_stream_dropdown_options();
            const options = [
                direct_messages_option,
                ...additional_settings,
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
            const user_selected_option = stream_input_dropdown_widget.value();
            if (
                user_selected_option === direct_messages_option.unique_id ||
                user_selected_option === map_to_channels_option.unique_id
            ) {
                $override_topic.prop("checked", false).prop("disabled", true);
                $override_topic.closest(".input-group").addClass("control-label-disabled");
                $topic_input.val("");
            } else {
                $override_topic.prop("disabled", false);
                $override_topic.closest(".input-group").removeClass("control-label-disabled");
            }
            $override_topic.trigger("change");

            dropdown.hide();
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

            $override_topic.prop("checked", false).prop("disabled", true);
            $override_topic.closest(".input-group").addClass("control-label-disabled");
            $topic_input.val("");
            $topic_input.parent().addClass("hide");

            stream_input_dropdown_widget.render(direct_messages_option.unique_id);
            $config_container.empty();
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
