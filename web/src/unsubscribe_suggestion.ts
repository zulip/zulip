import $ from "jquery";

import render_unsubscribe_suggestion_modal from "../templates/unsubscribe_suggestion_modal.hbs";

import * as browser_history from "./browser_history.ts";
import * as channel from "./channel.ts";
import { $t } from "./i18n.ts";
import * as modals from "./modals.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_settings_api from "./stream_settings_api.ts";
import * as sub_store from "./sub_store.ts";
import * as ui_report from "./ui_report.ts";
import * as unread from "./unread.ts";

export function launch(): void {
    const subscribed_streams = stream_data.subscribed_subs();

    // Calculate unread counts and sort
    const streams_with_counts = subscribed_streams.map((sub) => {
        const count_info = unread.unread_count_info_for_stream(sub.stream_id);
        return {
            ...sub,
            unread_count: count_info.unmuted_count + count_info.muted_count,
            is_muted: sub.is_muted,
        };
    });

    // Sort by unread count descending
    streams_with_counts.sort((a, b) => b.unread_count - a.unread_count);

    // Take top 50 to avoid overwhelming
    const top_streams = streams_with_counts.slice(0, 50);

    const html = render_unsubscribe_suggestion_modal({
        streams: top_streams,
    });

    modals.open("unsubscribe-suggestion-modal", {
        autoremove: true,
        on_show: () => {
            $("#unsubscribe-suggestion-modal .modal__container").html(html);

            $("#unsubscribe-suggestion-modal .mute-stream").on("click", (e) => {
                const stream_id = Number($(e.currentTarget).attr("data-stream-id"));
                const sub = sub_store.get(stream_id);
                if (sub) {
                    stream_settings_api.set_stream_property(sub, {
                        property: "is_muted",
                        value: !sub.is_muted,
                    });
                    // Visual feedback: toggle button text/state or remove row?
                    // For now, simple textual change or disable
                    $(e.currentTarget).text($t({ defaultMessage: "Muted" }));
                    $(e.currentTarget).prop("disabled", true);
                }
            });

            $("#unsubscribe-suggestion-modal .unsubscribe-stream").on("click", (e) => {
                const stream_id = Number($(e.currentTarget).attr("data-stream-id"));
                const sub = sub_store.get(stream_id);
                if (sub) {
                    channel.del({
                        url: "/json/users/me/subscriptions",
                        data: { subscriptions: JSON.stringify([sub.name]) },
                        success() {
                            // Remove row
                            $(e.currentTarget).closest(".recommendation-row").remove();
                        },
                        error(xhr) {
                            ui_report.error($t({ defaultMessage: "Failed" }), xhr, $("#unsubscribe-suggestion-modal-error"));
                        }
                    });
                }
            });
        },
        on_hidden: () => {
            browser_history.exit_overlay();
        },
    });
}
