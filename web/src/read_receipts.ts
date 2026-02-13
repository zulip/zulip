import $ from "jquery";
import assert from "minimalistic-assert";
import SimpleBar from "simplebar";
import type * as tippy from "tippy.js";
import * as z from "zod/mini";

import render_read_receipts from "../templates/read_receipts.hbs";
import render_read_receipts_modal from "../templates/read_receipts_modal.hbs";

import * as channel from "./channel.ts";
import {$t, $t_html} from "./i18n.ts";
import * as loading from "./loading.ts";
import * as message_store from "./message_store.ts";
import * as people from "./people.ts";
import * as popover_menus from "./popover_menus.ts";
import {realm} from "./state_data.ts";
import * as ui_report from "./ui_report.ts";
import {parse_html} from "./ui_util.ts";
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
        $("#read-receipts-popover .read_receipts_info").text(
            $t({
                defaultMessage: "Read receipts are not available for Notification Bot messages.",
            }),
        );
        $("#read-receipts-popover .read-receipt-content").addClass("compact");
        return;
    }
    if (!realm.realm_enable_read_receipts) {
        ui_report.error(
            $t({
                defaultMessage: "Read receipts are disabled for this organization.",
            }),
            undefined,
            $("#read-receipts-popover #read_receipts_error"),
        );
        return;
    }

    if (!has_initial_data) {
        loading.make_indicator($("#read-receipts-popover .loading_indicator"), {
            abs_positioned: true,
        });
    }

    void channel.get({
        url: `/json/messages/${message_id}/read_receipts`,
        success(raw_data) {
            const $modal = $("#read-receipts-popover").filter(`[data-message-id=${message_id}]`);
            // If the read receipts modal for the selected message ID is closed
            // by the time we receive the response, return immediately.
            if ($modal.length === 0) {
                return;
            }

            has_initial_data = true;
            $("#read-receipts-popover .read_receipts_error").removeClass("show");
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
                $("#read-receipts-popover .read_receipts_info").text(
                    $t({defaultMessage: "No one has read this message yet."}),
                );
                $modal.find(".read_receipts_list").hide();
            } else {
                $("#read-receipts-popover .read_receipts_info").html(
                    $t_html(
                        {
                            defaultMessage:
                                "{num_of_people, plural, one {<z-link>Read</z-link> by {num_of_people} person:} other {<z-link>Read</z-link> by {num_of_people} people:}}",
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
                $("#read-receipts-popover .read-receipt-container").addClass(
                    "showing_read_receipts_list",
                );
                new SimpleBar(util.the($("#read-receipts-popover .read-receipt-content")), {
                    tabIndex: -1,
                });
            }
            loading.destroy_indicator($("#read-receipts-popover .loading_indicator"));
        },
        error(xhr) {
            ui_report.error(
                $t({defaultMessage: "Failed to load read receipts."}),
                xhr,
                $("#read-receipts-popover #read_receipts_error"),
            );
            loading.destroy_indicator($("#read-receipts-popover .loading_indicator"));
        },
    });
}

export function open_read_receipt_popover(
    message_id: number,
    target: tippy.ReferenceElement,
): void {
    popover_menus.toggle_popover_menu(target, {
        theme: "popover-menu",
        placement: "bottom",
        popperOptions: {
            modifiers: [
                {
                    // The placement is set to bottom, but if that placement does not fit,
                    // the opposite top placement will be used.
                    name: "flip",
                    options: {
                        fallbackPlacements: ["top", "left"],
                    },
                },
            ],
        },
        onShow(instance) {
            instance.setContent(parse_html(render_read_receipts_modal({message_id})));
            popover_menus.popover_instances.read_receipt_popover = instance;

            has_initial_data = false;
            fetch_read_receipts(message_id);
            interval_id = window.setInterval(() => {
                fetch_read_receipts(message_id);
            }, read_receipts_polling_interval_ms);
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.read_receipt_popover = null;

            if (interval_id !== null) {
                clearInterval(interval_id);
                interval_id = null;
            }
        },
    });
}

export function toggle_read_receipts(message_id: number): void {
    const popover = popover_menus.popover_instances.read_receipt_popover;

    if (popover) {
        popover.hide();
        return;
    }

    open_read_receipt_popover(
        message_id,
        util.the($(`.message_row[data-message-id="${message_id}"]`)),
    );
}
