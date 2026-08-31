import {$} from "jquery";
import * as z from "zod/mini";

import render_compose_banner from "../templates/compose_banner/compose_banner.hbs";
import render_topic_drift_modal from "../templates/topic_drift_modal.hbs";

import * as channel from "./channel.ts";
import * as compose_banner from "./compose_banner.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t} from "./i18n.ts";
import * as loading from "./loading.ts";
import * as message_edit from "./message_edit.ts";
import * as modals from "./modals.ts";
import * as settings_data from "./settings_data.ts";
import * as ui_report from "./ui_report.ts";

const topic_drift_response_schema = z.object({
    has_drift: z.boolean(),
    current_title: z.string(),
    suggested_title: z.nullable(z.string()),
    reason: z.nullable(z.string()),
    stream_id: z.number(),
    topic_name: z.string(),
    message_id: z.nullable(z.number()),
});

export type TopicDriftResponse = z.infer<typeof topic_drift_response_schema>;

export function rename_topic_to_suggested(
    stream_id: number,
    old_topic_name: string,
    new_topic_name: string,
    message_id?: number | null,
    on_complete?: () => void,
): void {
    function execute_rename(target_message_id: number): void {
        channel.patch({
            url: "/json/messages/" + target_message_id,
            data: {
                topic: new_topic_name,
                propagate_mode: "change_all",
                send_notification_to_new_thread: true,
                send_notification_to_old_thread: true,
            },
            success() {
                // Clear any drift warning banners
                $(`#compose_banners .${CSS.escape(compose_banner.CLASSNAMES.topic_drift_suggestion)}`).remove();
                if (on_complete) {
                    on_complete();
                }
            },
            error(xhr) {
                const error_message = channel.xhr_error_message($t({defaultMessage: "Failed to rename topic"}), xhr);
                ui_report.client_error(error_message, $("#compose_banners"));
            },
        });
    }

    if (message_id !== undefined && message_id !== null) {
        execute_rename(message_id);
    } else {
        message_edit.with_first_message_id(stream_id, old_topic_name, (first_id) => {
            if (first_id !== undefined) {
                execute_rename(first_id);
            }
        });
    }
}

export function show_topic_drift_banner(data: TopicDriftResponse): void {
    if (!data.has_drift || !data.suggested_title) {
        return;
    }

    const suggested_title = data.suggested_title;
    const banner_text = data.reason
        ? $t(
              {
                  defaultMessage:
                      "Topic drift detected: {reason} Suggested new title: \"{suggested_title}\"",
              },
              {
                  reason: data.reason,
                  suggested_title,
              },
          )
        : $t(
              {
                  defaultMessage:
                      "Topic discussion seems to have drifted. Suggested new title: \"{suggested_title}\"",
              },
              {
                  suggested_title,
              },
          );

    const button_text = $t(
        {
            defaultMessage: "Rename topic to \"{suggested_title}\"",
        },
        {
            suggested_title,
        },
    );

    const banner_html = render_compose_banner({
        banner_type: compose_banner.WARNING,
        classname: compose_banner.CLASSNAMES.topic_drift_suggestion,
        banner_text,
        button_text,
        stream_id: data.stream_id,
        topic_name: data.topic_name,
    });

    const $banner = $(banner_html);
    const $container = $("#compose_banners");

    $banner.on("click", ".main-view-banner-action-button", (e) => {
        e.preventDefault();
        rename_topic_to_suggested(
            data.stream_id,
            data.topic_name,
            suggested_title,
            data.message_id,
        );
    });

    compose_banner.update_or_append_banner(
        $banner,
        compose_banner.CLASSNAMES.topic_drift_suggestion,
        $container,
    );
}

export function check_topic_drift_for_sent_message(
    stream_id: number,
    topic_name: string,
    message_id?: number | null,
): void {
    if (!settings_data.user_can_summarize_topics()) {
        return;
    }

    if (!topic_name || topic_name.trim() === "") {
        return;
    }

    channel.post({
        url: "/json/topics/check_drift",
        data: {
            stream_id,
            topic_name,
            message_id: message_id ?? undefined,
        },
        success(response_data) {
            const data = topic_drift_response_schema.parse(response_data);
            if (data.has_drift) {
                show_topic_drift_banner(data);
            }
        },
        error() {
            // Silently ignore background drift check errors to not interrupt sending flow
        },
    });
}

export function improve_topic_title_interactive(
    stream_id: number,
    topic_name: string,
): void {
    dialog_widget.launch({
        modal_title_text: $t({defaultMessage: "Improve Topic Title (AI)"}),
        modal_content_html: "<div id='topic-drift-modal-content'><div id='topic-drift-loading-container'></div></div>",
        close_on_submit: true,
        id: "improve-topic-title-modal",
        footer_minor_text: $t({
            defaultMessage: "AI analyzes recent messages in this topic to detect topic drift.",
        }),
        modal_submit_button_text: $t({defaultMessage: "Close"}),
        single_footer_button: true,
        on_click() {
            // Close the modal
        },
        on_show() {
            const $loading_container = $("#topic-drift-loading-container");
            loading.make_indicator($loading_container, {
                text: $t({defaultMessage: "Analyzing topic messages for drift with AI..."}),
            });
        },
        post_render() {
            const close_on_success = false;
            dialog_widget.submit_api_request(
                channel.post,
                "/json/topics/check_drift",
                {
                    stream_id,
                    topic_name,
                },
                {
                    success_continuation(response_data) {
                        const data = topic_drift_response_schema.parse(response_data);
                        const $modal_content = $("#topic-drift-modal-content");

                        const html = render_topic_drift_modal({
                            has_drift: data.has_drift,
                            current_title: data.current_title,
                            suggested_title: data.suggested_title,
                            reason: data.reason,
                        });
                        $modal_content.html(html);

                        if (data.has_drift && data.suggested_title) {
                            $modal_content.on("click", "#apply-improved-topic-title-btn", () => {
                                const new_title = $("#suggested-topic-title-input").val();
                                if (typeof new_title === "string" && new_title.trim() !== "") {
                                    rename_topic_to_suggested(
                                        stream_id,
                                        topic_name,
                                        new_title.trim(),
                                        data.message_id,
                                        () => {
                                            modals.close_active();
                                        },
                                    );
                                }
                            });
                        }
                    },
                    error_continuation(xhr) {
                        const $modal_content = $("#topic-drift-modal-content");
                        const error_message = channel.xhr_error_message(
                            $t({defaultMessage: "Failed to analyze topic drift"}),
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
