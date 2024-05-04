import ClipboardJS from "clipboard";
import $ from "jquery";
import type {Instance} from "tippy.js";

import render_generate_integration_url_modal from "../templates/settings/generate_integration_url_modal.hbs";
import render_integration_events from "../templates/settings/integration_events.hbs";

import {show_copied_confirmation} from "./copied_tooltip";
import * as dialog_widget from "./dialog_widget";
import * as dropdown_widget from "./dropdown_widget";
import type {DropdownWidget, Option} from "./dropdown_widget";
import {$t_html} from "./i18n";
import {realm} from "./state_data";
import * as stream_data from "./stream_data";
import * as util from "./util";

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
    const html_body = render_generate_integration_url_modal({
        default_url_message,
        max_topic_length: realm.max_topic_length,
    });

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

        $dialog_submit_button.prop("disabled", true);
        $("#integration-url-stream_widget").prop("disabled", true);

        const clipboard = new ClipboardJS("#generate-integration-url-modal .dialog_submit_button", {
            text() {
                return $integration_url.text();
            },
        });
        clipboard.on("success", () => {
            show_copied_confirmation($("#generate-integration-url-modal .dialog_submit_button")[0]);
        });

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

            const selected_integration_data = realm.realm_incoming_webhook_bots.find(
                (bot) => bot.name === selected_integration,
            );
            const all_event_types = selected_integration_data?.all_event_types;

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
                if ($override_topic.prop("checked") && topic_name !== "") {
                    params.set("topic", topic_name);
                }
            }
            const selected_events = set_events_param(params);

            const realm_url = realm.realm_uri;
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
            tippy_props: {
                placement: "bottom-start",
            },
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
            dropdown: Instance,
        ): void {
            integration_input_dropdown_widget.render();
            $(".integration-url-name-wrapper").trigger("input");

            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
        }

        stream_input_dropdown_widget = new dropdown_widget.DropdownWidget({
            widget_name: "integration-url-stream",
            get_options: get_options_for_stream_dropdown_widget,
            item_click_callback: stream_item_click_callback,
            $events_container: $("#generate-integration-url-modal"),
            tippy_props: {
                placement: "bottom-start",
            },
            default_id: direct_messages_option.unique_id,
            unique_id_type: dropdown_widget.DataTypes.NUMBER,
        });
        stream_input_dropdown_widget.setup();

        function get_options_for_stream_dropdown_widget(): Option[] {
            const options = [
                direct_messages_option,
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

        function stream_item_click_callback(event: JQuery.ClickEvent, dropdown: Instance): void {
            stream_input_dropdown_widget.render();
            $(".integration-url-stream-wrapper").trigger("input");
            const user_selected_option = stream_input_dropdown_widget.value();
            if (user_selected_option === direct_messages_option.unique_id) {
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
    });
}
