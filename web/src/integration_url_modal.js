import ClipboardJS from "clipboard";
import $ from "jquery";

import render_generate_integration_url_modal from "../templates/settings/generate_integration_url_modal.hbs";

import {show_copied_confirmation} from "./copied_tooltip";
import * as dialog_widget from "./dialog_widget";
import * as dropdown_widget from "./dropdown_widget";
import {$t_html} from "./i18n";
import {realm} from "./state_data";
import * as stream_data from "./stream_data";
import * as util from "./util";

export function show_generate_integration_url_modal(api_key) {
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

    function generate_integration_url_post_render() {
        let selected_integration = "";
        let stream_input_dropdown_widget;
        let integration_input_dropdown_widget;

        const $override_topic = $("#integration-url-override-topic");
        const $topic_input = $("#integration-url-topic-input");
        const $integration_url = $("#generate-integration-url-modal .integration-url");
        const $dialog_submit_button = $("#generate-integration-url-modal .dialog_submit_button");

        $dialog_submit_button.prop("disabled", true);

        new ClipboardJS("#generate-integration-url-modal .dialog_submit_button", {
            text() {
                return $integration_url.text();
            },
        }).on("success", (e) => {
            show_copied_confirmation(e.trigger);
        });

        $override_topic.on("change", function () {
            const checked = $(this).prop("checked");
            $topic_input.parent().toggleClass("hide", !checked);
        });

        $("#generate-integration-url-modal .integration-url-parameter").on("change input", () => {
            update_url();
        });

        function update_url() {
            selected_integration = integration_input_dropdown_widget.value();
            if (selected_integration === default_integration_option.unique_id) {
                $integration_url.text(default_url_message);
                $dialog_submit_button.prop("disabled", true);
                return;
            }

            const stream_id = stream_input_dropdown_widget.value();
            const topic_name = $topic_input.val();

            const params = new URLSearchParams({api_key});
            if (stream_id !== -1) {
                params.set("stream", stream_id);
                if (topic_name !== "") {
                    params.set("topic", topic_name);
                }
            }

            const realm_url = realm.realm_uri;
            const base_url = `${realm_url}/api/v1/external/`;
            $integration_url.text(`${base_url}${selected_integration}?${params}`);
            $dialog_submit_button.prop("disabled", false);

            if ($override_topic.prop("checked") && topic_name === "") {
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
            unique_id_type: dropdown_widget.DATA_TYPES.STRING,
        });
        integration_input_dropdown_widget.setup();

        function get_options_for_integration_input_dropdown_widget() {
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

        function integration_item_click_callback(event, dropdown) {
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
            unique_id_type: dropdown_widget.DATA_TYPES.NUMBER,
        });
        stream_input_dropdown_widget.setup();

        function get_options_for_stream_dropdown_widget() {
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

        function stream_item_click_callback(event, dropdown) {
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
    }

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Generate URL for an integration"}),
        html_body,
        id: "generate-integration-url-modal",
        html_submit_button: $t_html({defaultMessage: "Copy URL"}),
        html_exit_button: $t_html({defaultMessage: "Close"}),
        on_click() {},
        post_render: generate_integration_url_post_render,
    });
}
