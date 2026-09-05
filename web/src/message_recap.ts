import {$} from "jquery";
import * as z from "zod/mini";

import render_message_recap from "../templates/message_recap.hbs";

import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t} from "./i18n.ts";
import * as loading from "./loading.ts";
import * as modals from "./modals.ts";
import * as rendered_markdown from "./rendered_markdown.ts";
import * as ui_report from "./ui_report.ts";

export function show_message_recap(): void {
    dialog_widget.launch({
        modal_title_text: $t({defaultMessage: "Unread Messages Recap"}),
        modal_content_html: "<div id='message-recap-loading-container'></div>",
        close_on_submit: true,
        id: "message-recap-modal",
        footer_minor_text: $t({
            defaultMessage: "AI recaps may have errors. Click message links to jump to context.",
        }),
        modal_submit_button_text: $t({defaultMessage: "Close"}),
        single_footer_button: true,
        on_click() {
            // Close the modal
        },
        on_show() {
            const $loading_container = $("#message-recap-loading-container");
            loading.make_indicator($loading_container, {
                text: $t({defaultMessage: "Generating recap of unread messages with AI..."}),
            });
        },
        post_render() {
            const close_on_success = false;
            dialog_widget.submit_api_request(
                channel.get,
                "/json/messages/recap",
                {},
                {
                    success_continuation(response_data) {
                        const data = z
                            .object({
                                recap: z.string(),
                                has_unreads: z.optional(z.boolean()),
                            })
                            .parse(response_data);

                        const recap_markdown = data.recap;
                        const recap_html = render_message_recap({
                            recap_markdown,
                        });

                        const $modal_content = $("#message-recap-modal .modal__content");
                        $modal_content
                            .removeClass("hide")
                            .addClass("rendered_markdown")
                            .html(recap_html);

                        rendered_markdown.update_elements($modal_content);

                        // When user clicks any narrow link inside the recap, close the modal so they view the message
                        $modal_content.on("click", "a[href^='#narrow']", () => {
                            modals.close_active();
                        });
                    },
                    error_continuation(xhr) {
                        const $modal_content = $("#message-recap-modal .modal__content");
                        const error_message = channel.xhr_error_message(
                            $t({defaultMessage: "Failed to generate recap"}),
                            xhr,
                        );
                        ui_report.error(error_message, xhr, $modal_content);
                    },
                },
                close_on_success,
            );
        },
    });
}
