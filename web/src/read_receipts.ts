import $ from "jquery";
import assert from "minimalistic-assert";
import SimpleBar from "simplebar";
import * as z from "zod/mini";

import render_read_receipts from "../templates/read_receipts.hbs";
import render_read_receipts_modal from "../templates/read_receipts_modal.hbs";

import * as channel from "./channel.ts";
import {$t, $t_html} from "./i18n.ts";
import * as loading from "./loading.ts";
import * as message_store from "./message_store.ts";
import * as modals from "./modals.ts";
import * as people from "./people.ts";
import {realm} from "./state_data.ts";
import * as ui_report from "./ui_report.ts";
import * as util from "./util.ts";

const read_receipts_polling_interval_ms = 60 * 1000;
const read_receipts_api_response_schema = z.object({
    user_ids: z.array(z.number()),
});

let interval_id: number | null = null;
let has_initial_data = false;

export function fetch_read_receipts(message_id: number): void {
    const message = message_store.get(message_id);
    assert(message !== undefined, "message is undefined");

    if (message.sender_email === "notification-bot@zulip.com") {
        $("#read_receipts_modal .read_receipts_info").text(
            $t({
                defaultMessage: "Read receipts are not available for Notification Bot messages.",
            }),
        );
        $("#read_receipts_modal .modal__content").addClass("compact");
        return;
    }
    if (!realm.realm_enable_read_receipts) {
        ui_report.error(
            $t({
                defaultMessage: "Read receipts are disabled for this organization.",
            }),
            undefined,
            $("#read_receipts_modal #read_receipts_error"),
        );
        return;
    }

    if (!has_initial_data) {
        loading.make_indicator($("#read_receipts_modal .loading_indicator"));
    }

    void channel.get({
        url: `/json/messages/${message_id}/read_receipts`,
        success(raw_data) {
            const $modal = $("#read_receipts_modal").filter(`[data-message-id=${message_id}]`);
            // If the read receipts modal for the selected message ID is closed
            // by the time we receive the response, return immediately.
            if ($modal.length === 0) {
                return;
            }

            has_initial_data = true;
            $("#read_receipts_modal .read_receipts_error").removeClass("show");
            const data = read_receipts_api_response_schema.parse(raw_data);
            const users = data.user_ids.map((id) => people.get_user_by_id_assert_valid(id));
            users.sort(people.compare_by_name);

            const context = {
                users: users.map((user) => ({
                    user_id: user.user_id,
                    full_name: user.full_name,
                    avatar_url: people.small_avatar_url_for_person(user),
                })),
            };

            if (users.length === 0) {
                $("#read_receipts_modal .read_receipts_info").text(
                    $t({defaultMessage: "No one has read this message yet."}),
                );
                $modal.find(".read_receipts_list").hide();
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
                $modal.find(".read_receipts_list").html(render_read_receipts(context)).show();
                $("#read_receipts_modal .modal__container").addClass("showing_read_receipts_list");
                new SimpleBar(util.the($("#read_receipts_modal .modal__content")), {
                    tabIndex: -1,
                });
            }
            loading.destroy_indicator($("#read_receipts_modal .loading_indicator"));
        },
        error(xhr) {
            ui_report.error(
                $t({defaultMessage: "Failed to load read receipts."}),
                xhr,
                $("#read_receipts_modal #read_receipts_error"),
            );
            loading.destroy_indicator($("#read_receipts_modal .loading_indicator"));
        },
    });
}

export function show_user_list(message_id: number): void {
    $("#read-receipts-modal-container").html(render_read_receipts_modal({message_id}));
    modals.open("read_receipts_modal", {
        autoremove: true,
        on_shown() {
            has_initial_data = false;
            fetch_read_receipts(message_id);
            interval_id = window.setInterval(() => {
                fetch_read_receipts(message_id);
            }, read_receipts_polling_interval_ms);
        },
        on_hidden() {
            if (interval_id !== null) {
                clearInterval(interval_id);
                interval_id = null;
            }
        },
    });
}

export function hide_user_list(): void {
    modals.close_if_open("read_receipts_modal");
}
