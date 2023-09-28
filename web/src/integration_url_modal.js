import ClipboardJS from "clipboard";
import $ from "jquery";

import render_generate_integration_url_modal from "../templates/settings/generate_integration_url_modal.hbs";

import {show_copied_confirmation} from "./copied_tooltip";
import * as dialog_widget from "./dialog_widget";
import * as dropdown_widget from "./dropdown_widget";
import {$t_html} from "./i18n";
import {page_params} from "./page_params";
import * as stream_data from "./stream_data";

export function show_generate_integration_url_modal(api_key) {
    const default_url_message = $t_html({defaultMessage: "Integration URL will appear here."});
    const streams = stream_data.subscribed_subs();
    const direct_messages_option = {
        name: $t_html({defaultMessage: "Direct message to me"}),
        unique_id: "",
        is_direct_message: true,
    };
    const html_body = render_generate_integration_url_modal({
        default_url_message,
        max_topic_length: page_params.max_topic_length,
    });

    function generate_integration_url_post_render() {
        let selected_integration = "";
        let stream_input_dropdown_widget;

        const $integration_input = $("#integration-input");
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

        $integration_input
            .typeahead({
                items: 5,
                fixed: true,
                source: () =>
                    page_params.realm_incoming_webhook_bots.map((bot) => bot.display_name),
                updater(item) {
                    selected_integration = page_params.realm_incoming_webhook_bots.find(
                        (bot) => bot.display_name === item,
                    ).name;
                    return item;
                },
            })
            .on("input", function () {
                const current_value = $(this).val();
                if (current_value === "") {
                    selected_integration = "";
                }
            });

        $override_topic.on("change", function () {
            const checked = $(this).prop("checked");
            $topic_input.parent().toggleClass("hide", !checked);
        });

        $("#generate-integration-url-modal .integration-url-parameter").on("change input", () => {
            update_url();
        });

        function update_url() {
            if (selected_integration === "") {
                $integration_url.text(default_url_message);
                $dialog_submit_button.prop("disabled", true);
                return;
            }

            const stream_name = stream_input_dropdown_widget.value();
            const topic_name = $topic_input.val();

            const params = new URLSearchParams({api_key});
            if (stream_name !== "") {
                params.set("stream", stream_name);
                if (topic_name !== "") {
                    params.set("topic", topic_name);
                }
            }

            const realm_url = page_params.realm_uri;
            const base_url = `${realm_url}/api/v1/external/`;
            $integration_url.text(`${base_url}${selected_integration}?${params}`);
            $dialog_submit_button.prop("disabled", false);
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
            unique_id_type: dropdown_widget.DATA_TYPES.STRING,
        });
        stream_input_dropdown_widget.setup();

        function get_options_for_stream_dropdown_widget() {
            const options = [
                direct_messages_option,
                ...streams.map((stream) => ({
                    name: stream.name,
                    unique_id: stream.name,
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
