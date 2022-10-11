import $ from "jquery";
import SimpleBar from "simplebar";

import render_read_receipts from "../templates/read_receipts.hbs";
import render_read_receipts_modal from "../templates/read_receipts_modal.hbs";

import * as channel from "./channel";
import {$t, $t_html} from "./i18n";
import * as loading from "./loading";
import * as message_store from "./message_store";
import * as overlays from "./overlays";
import * as people from "./people";
import * as popovers from "./popovers";
import * as ui_report from "./ui_report";

export function show_user_list(message_id) {
    $("body").append(render_read_receipts_modal());
    overlays.open_modal("read_receipts_modal", {
        autoremove: true,
        on_show() {
            const message = message_store.get(message_id);
            if (message.sender_email === "notification-bot@zulip.com") {
                $("#read_receipts_modal .read_receipts_info").text(
                    $t({
                        defaultMessage:
                            "Read receipts are not available for Notification Bot messages.",
                    }),
                );
                $("#read_receipts_modal .modal__content").addClass("compact");
            } else {
                loading.make_indicator($("#read_receipts_modal .loading_indicator"));
                channel.get({
                    url: `/json/messages/${message_id}/read_receipts`,
                    success(data) {
                        const users = data.user_ids.map((id) => {
                            const user = people.get_by_user_id(id);
                            return {
                                user_id: user.user_id,
                                full_name: user.full_name,
                                avatar_url: people.small_avatar_url_for_person(user),
                            };
                        });
                        users.sort(people.compare_by_name);

                        loading.destroy_indicator($("#read_receipts_modal .loading_indicator"));
                        if (users.length === 0) {
                            $("#read_receipts_modal .read_receipts_info").text(
                                $t({defaultMessage: "No one has read this message yet."}),
                            );
                        } else {
                            $("#read_receipts_modal .read_receipts_info").html(
                                $t_html(
                                    {
                                        defaultMessage:
                                            "{num_of_people, plural, one {This message has been <z-link>read</z-link> by {num_of_people} person:} other {This message has been <z-link>read</z-link> by {num_of_people} people:}}",
                                    },
                                    {
                                        num_of_people: users.length,
                                        "z-link": (content_html) =>
                                            `<a href="/help/read-receipts" target="_blank" rel="noopener noreferrer">${content_html.join(
                                                "",
                                            )}</a>`,
                                    },
                                ),
                            );
                            $("#read_receipts_modal .modal__container").addClass(
                                "showing_read_receipts_list",
                            );
                            $("#read_receipts_modal .modal__content").append(
                                render_read_receipts({users}),
                            );
                            new SimpleBar($("#read_receipts_modal .modal__content")[0]);
                        }
                    },
                    error(xhr) {
                        ui_report.error("", xhr, $("#read_receipts_error"));
                        loading.destroy_indicator($("#read_receipts_modal .loading_indicator"));
                    },
                });
            }
        },
        on_hide() {
            // Ensure any user info popovers are closed
            popovers.hide_all();
        },
    });
}
