import {$} from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";
import * as z from "zod/mini";

import render_read_receipts from "../templates/read_receipts.hbs";
import render_read_receipts_popover from "../templates/read_receipts_popover.hbs";

import * as channel from "./channel.ts";
import {$t, $t_html} from "./i18n.ts";
import * as loading from "./loading.ts";
import * as message_lists from "./message_lists.ts";
import * as message_store from "./message_store.ts";
import * as people from "./people.ts";
import * as popover_menus from "./popover_menus.ts";
import * as popovers from "./popovers.ts";
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

// A poll response can arrive after the popover was closed, or reopened for
// another message; both must be ignored.
function get_popover_for_message(message_id: number): JQuery {
    return $("#read-receipts-popover").filter(`[data-message-id=${message_id}]`);
}

// Look up the button in the current message list, not the whole document,
// since the same message can appear in several lists.
function get_message_actions_menu_button(message_id: number): JQuery {
    const $row = message_lists.current?.get_row(message_id);
    if ($row === undefined) {
        return $();
    }
    return $row.find(".actions_hover .message-actions-menu-button");
}

export function clear_for_testing(): void {
    has_initial_data = false;
    interval_id = null;
}

export function fetch_read_receipts(message_id: number): void {
    const message = message_store.get(message_id);
    assert(message !== undefined, "message is undefined");

    if (message.sender_email === "notification-bot@zulip.com") {
        $("#read-receipts-popover .read_receipts_info").text(
            $t({
                defaultMessage: "Read receipts are not available for Notification Bot messages.",
            }),
        );
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
            const $popover = get_popover_for_message(message_id);
            if ($popover.length === 0) {
                return;
            }

            has_initial_data = true;
            // empty + reset the inline display fadeTo sets, else the box lingers.
            $("#read-receipts-popover #read_receipts_error")
                .empty()
                .removeClass("show")
                .css("display", "");
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
                $popover.find(".read_receipts_list").hide();
            } else {
                $("#read-receipts-popover .read_receipts_info").html(
                    $t_html(
                        {
                            defaultMessage:
                                "{num_of_people, plural, one {Message <z-link>read</z-link> by {num_of_people} person:} other {Message <z-link>read</z-link> by {num_of_people} people:}}",
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
                $popover.find(".read_receipts_list").html(render_read_receipts(context)).show();
            }
            loading.destroy_indicator($("#read-receipts-popover .loading_indicator"));
        },
        error(xhr) {
            if (get_popover_for_message(message_id).length === 0) {
                return;
            }

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
    focus_on_open = false,
): void {
    let return_to_message_actions_menu = false;
    popover_menus.toggle_popover_menu(target, {
        theme: "popover-menu",
        placement: "bottom",
        // Don't dismiss on any outside click; a user card opened from the list
        // is a separate popover, and clicking it should not close this one.
        hideOnClick: false,
        onClickOutside(instance, event) {
            if (
                event.target instanceof Element &&
                event.target.closest(
                    ".user-card-popover-root, .message-user-card-popover-root, .user-sidebar-popover-root",
                )
            ) {
                return;
            }
            instance.hide();
        },
        popperOptions: {
            modifiers: [
                {
                    // Prefer below the button, then above, then beside it.
                    name: "flip",
                    options: {
                        fallbackPlacements: ["top", "left"],
                    },
                },
            ],
        },
        onShow(instance) {
            // No on_show_prep: it stops clicks propagating, but opening a
            // reader's user card needs the global click handler.
            instance.setContent(parse_html(render_read_receipts_popover({message_id})));
            popover_menus.popover_instances.read_receipt_popover = instance;
            const $row = $(instance.reference).closest(".message_row");
            $row.addClass("has_actions_popover");
        },
        onMount(instance) {
            // Fetch in onMount, not onShow: the loading indicator is added by
            // querying the popover, which isn't in the DOM yet during onShow.
            has_initial_data = false;
            fetch_read_receipts(message_id);
            interval_id = window.setInterval(() => {
                fetch_read_receipts(message_id);
            }, read_receipts_polling_interval_ms);

            // The header is a back button. We reopen the message actions menu
            // in onHidden, after this one closes, so they don't fight over the
            // row's has_actions_popover class.
            $(instance.popper).on("click", ".read-receipts-header", (e) => {
                e.preventDefault();
                e.stopPropagation();
                return_to_message_actions_menu = true;
                // hide_all, not instance.hide, so the header's tooltip and any
                // user card opened from the list go away too.
                popovers.hide_all();
            });

            // On keyboard open, move focus into the popover so it's reachable
            // and off the message actions button. We focus the container, not
            // an item, so no ring shows until the user arrows or tabs.
            if (focus_on_open) {
                $(instance.popper).find("#read-receipts-popover").trigger("focus");
            }
        },
        onHidden(instance) {
            const $row = $(instance.reference).closest(".message_row");
            $row.removeClass("has_actions_popover");
            instance.destroy();
            popover_menus.popover_instances.read_receipt_popover = null;

            if (interval_id !== null) {
                clearInterval(interval_id);
                interval_id = null;
            }

            if (return_to_message_actions_menu) {
                return_to_message_actions_menu = false;
                // Look the button up again; the one we opened from is detached
                // if the row rerendered, and clicking that does nothing.
                get_message_actions_menu_button(message_id).trigger("click");
            }
        },
    });
}

export function toggle_read_receipts(message_id: number): void {
    if (popover_menus.popover_instances.read_receipt_popover) {
        // hide_all, not just this popover, so a user card opened from the
        // list doesn't outlive it.
        popovers.hide_all();
        return;
    }

    const $button = get_message_actions_menu_button(message_id);
    if ($button.length === 0) {
        return;
    }

    // Close any open message actions menu first; if it's on this same button,
    // opening on that reference would just toggle the menu shut.
    popover_menus.hide_current_popover_if_visible(popover_menus.popover_instances.message_actions);
    // This path is only reached from the keyboard, so open with focus.
    open_read_receipt_popover(message_id, util.the($button), true);
}
