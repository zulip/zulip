import {$} from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_message_actions_popover from "../templates/popovers/message_actions_popover.hbs";

import * as clipboard_handler from "./clipboard_handler.ts";
import * as compose_reply from "./compose_reply.ts";
import * as condense from "./condense.ts";
import {show_copied_confirmation} from "./copied_tooltip.ts";
import * as emoji_picker from "./emoji_picker.ts";
import * as message_delete from "./message_delete.ts";
import * as message_edit from "./message_edit.ts";
import * as message_lists from "./message_lists.ts";
import * as message_report from "./message_report.ts";
import type {Message} from "./message_store.ts";
import * as message_viewport from "./message_viewport.ts";
import * as popover_menus from "./popover_menus.ts";
import * as popover_menus_data from "./popover_menus_data.ts";
import * as popovers from "./popovers.ts";
import * as read_receipts from "./read_receipts.ts";
import * as rows from "./rows.ts";
import * as stream_popover from "./stream_popover.ts";
import {parse_html} from "./ui_util.ts";
import * as unread_ops from "./unread_ops.ts";
import {the} from "./util.ts";

let message_actions_popover_keyboard_toggle = false;

// What the message whose ⋮ button was last pressed should quote or forward,
// recorded on mousedown because the selection does not survive the click.
let quote_menu_selection_at_button_mousedown:
    {message_id: number; quote_menu_selection: compose_reply.QuoteMenuSelection} | undefined;

// What each open menu was rendered to quote or forward. Keyed by instance so
// that hiding one menu cannot disturb another that has since been opened.
const quote_menu_selection_by_instance = new WeakMap<
    tippy.Instance,
    compose_reply.QuoteMenuSelection
>();

function get_action_menu_menu_items(): JQuery {
    return $("[data-tippy-root] #message-actions-menu-dropdown li:not(.divider) a");
}

function quote_from_menu(
    message_id: number,
    quote_menu_selection: compose_reply.QuoteMenuSelection,
    forward_message: boolean,
): void {
    switch (quote_menu_selection.kind) {
        case "full_message":
            compose_reply.quote_messages({
                trigger: "popover respond",
                message_id,
                forward_message,
            });
            return;
        case "message_selection":
            compose_reply.quote_messages({
                trigger: "popover respond",
                message_id,
                quote_content: quote_menu_selection.quote_content,
                forward_message,
            });
            return;
        case "selected_messages":
            compose_reply.quote_messages({
                trigger: "popover respond",
                highlighted_message_ids: quote_menu_selection.message_ids,
                forward_message,
            });
            return;
    }
}

function focus_first_action_popover_item(): void {
    // For now I recommend only calling this when the user opens the menu with a hotkey.
    // Our popup menus act kind of funny when you mix keyboard and mouse.
    const $items = get_action_menu_menu_items();
    popover_menus.focus_first_popover_item($items);
}

export function toggle_message_actions_menu(message: Message): boolean {
    if (popover_menus.is_message_actions_popover_displayed()) {
        popovers.hide_all();
        return true;
    }

    if (message.locally_echoed || message_edit.currently_editing_messages.has(message.id)) {
        // Don't open the popup for locally echoed messages for now.
        // It creates bugs with things like keyboard handlers when
        // we get the server response.
        // We also suppress the popup for messages in an editing state,
        // including previews, when a user tries to reach them from the
        // keyboard.
        return true;
    }

    // Since this can be called via hotkey, we need to
    // hide any other popovers that may be open before.
    if (popovers.any_active()) {
        popovers.hide_all();
    }

    message_viewport.maybe_scroll_to_show_message_top();
    const $popover_reference = $(".selected_message .actions_hover .message-actions-menu-button");
    message_actions_popover_keyboard_toggle = true;
    // This synthetic click has no mousedown of its own, so make sure it
    // cannot consume a stale selection left behind by an earlier ⋮ press.
    quote_menu_selection_at_button_mousedown = undefined;
    $popover_reference.trigger("click");
    return true;
}

export function initialize({
    message_reminder_click_handler,
}: {
    message_reminder_click_handler: (
        remind_message_id: number,
        target: tippy.ReferenceElement,
    ) => void;
}): void {
    // Pressing the ⋮ button collapses any text selection on mouseup, well
    // before the popover opens, so we have to read the selection here.
    $("#main_div").on(
        "mousedown",
        ".actions_hover .message-actions-menu-button",
        function (this: HTMLElement) {
            const $row = $(this).closest(".message_row");
            if ($row.length === 0) {
                return;
            }
            const message_id = rows.id($row);
            quote_menu_selection_at_button_mousedown = {
                message_id,
                quote_menu_selection: compose_reply.get_quote_menu_selection(message_id),
            };
        },
    );

    popover_menus.register_popover_menu(".actions_hover .message-actions-menu-button", {
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
            popover_menus.on_show_prep(instance);
            const $row = $(instance.reference).closest(".message_row");
            const message_id = rows.id($row);
            // Mouse opens rely on what we read on mousedown; keyboard opens
            // have no mousedown, but do still have the live selection.
            const at_mousedown = quote_menu_selection_at_button_mousedown;
            quote_menu_selection_at_button_mousedown = undefined;
            const quote_menu_selection =
                at_mousedown?.message_id === message_id
                    ? at_mousedown.quote_menu_selection
                    : compose_reply.get_quote_menu_selection(message_id);
            quote_menu_selection_by_instance.set(instance, quote_menu_selection);
            const args = popover_menus_data.get_actions_popover_content_context(
                message_id,
                quote_menu_selection,
            );
            instance.setContent(parse_html(render_message_actions_popover(args)));
            $row.addClass("has_actions_popover");
        },
        onMount(instance) {
            const $row = $(instance.reference).closest(".message_row");
            const message_id = rows.id($row);
            const quote_menu_selection = quote_menu_selection_by_instance.get(instance);
            assert(quote_menu_selection !== undefined);
            if (message_actions_popover_keyboard_toggle) {
                focus_first_action_popover_item();
                message_actions_popover_keyboard_toggle = false;
            }
            popover_menus.popover_instances.message_actions = instance;

            // We want click events to propagate to `instance` so that
            // instance.hide gets called.
            const $popper = $(instance.popper);
            $popper.one("click", ".respond_button", (e) => {
                quote_from_menu(message_id, quote_menu_selection, false);
                e.preventDefault();
                e.stopPropagation();
                popover_menus.hide_current_popover_if_visible(instance);
            });

            $popper.one("click", ".forward_button", (e) => {
                quote_from_menu(message_id, quote_menu_selection, true);
                e.preventDefault();
                e.stopPropagation();
                popover_menus.hide_current_popover_if_visible(instance);
            });

            $popper.one("click", ".popover_edit_message, .popover_view_source", (e) => {
                const message_id = Number($(e.currentTarget).attr("data-message-id"));
                assert(message_lists.current !== undefined);
                const $row = message_lists.current.get_row(message_id);
                message_edit.start($row);
                e.preventDefault();
                e.stopPropagation();
                popover_menus.hide_current_popover_if_visible(instance);
            });

            $popper.one("click", ".message-reminder", (e) => {
                const remind_message_id = Number($(e.currentTarget).attr("data-message-id"));
                popover_menus.hide_current_popover_if_visible(instance);
                message_reminder_click_handler(remind_message_id, instance.reference);
                e.preventDefault();
                e.stopPropagation();
            });

            $popper.one("click", ".popover_move_message", (e) => {
                const message_id = Number($(e.currentTarget).attr("data-message-id"));
                assert(message_lists.current !== undefined);
                message_lists.current.select_id(message_id);
                const message = message_lists.current.get(message_id);
                assert(message?.type === "stream");
                void stream_popover.build_move_topic_to_stream_popover(
                    message.stream_id,
                    message.topic,
                    false,
                    message,
                );
                e.preventDefault();
                e.stopPropagation();
                popover_menus.hide_current_popover_if_visible(instance);
            });

            $popper.one("click", ".mark_as_unread", (e) => {
                const message_id = Number($(e.currentTarget).attr("data-message-id"));
                unread_ops.mark_as_unread_from_here(message_id);
                e.preventDefault();
                e.stopPropagation();
                popover_menus.hide_current_popover_if_visible(instance);
            });

            $popper.one("click", ".popover_toggle_collapse", (e) => {
                const message_id = Number($(e.currentTarget).attr("data-message-id"));
                assert(message_lists.current !== undefined);
                const message = message_lists.current.get(message_id);
                assert(message !== undefined);
                condense.toggle_collapse(message);
                e.preventDefault();
                e.stopPropagation();
                popover_menus.hide_current_popover_if_visible(instance);
            });

            $popper.one("click", ".view_read_receipts", (e) => {
                const message_id = Number($(e.currentTarget).attr("data-message-id"));
                read_receipts.show_user_list(message_id);
                e.preventDefault();
                e.stopPropagation();
                popover_menus.hide_current_popover_if_visible(instance);
            });

            $popper.one("click", ".delete_message", (e) => {
                const message_id = Number($(e.currentTarget).attr("data-message-id"));
                message_delete.delete_message(message_id);
                e.preventDefault();
                e.stopPropagation();
                popover_menus.hide_current_popover_if_visible(instance);
            });

            $popper.one("click", ".popover_report_message", (e) => {
                const message_id = Number($(e.currentTarget).attr("data-message-id"));
                assert(message_lists.current !== undefined);
                const message = message_lists.current.get(message_id);
                assert(message !== undefined);
                message_report.show_message_report_modal(message);
                e.preventDefault();
                e.stopPropagation();
                popover_menus.hide_current_popover_if_visible(instance);
            });

            $popper.one("click", ".reaction_button", (e) => {
                const message_id = Number($(e.currentTarget).attr("data-message-id"));
                // Don't propagate the click event since the emoji_picker code opens a
                // popover which we don't want to hide after actions popover is hidden.
                e.stopPropagation();
                e.preventDefault();
                assert(instance.reference.parentElement !== null);
                emoji_picker.start_picker_for_message_reaction(
                    instance.reference.parentElement,
                    message_id,
                );
                popover_menus.hide_current_popover_if_visible(instance);
            });

            $popper.on("click", ".copy_link", function (this: HTMLElement) {
                void (async () => {
                    await clipboard_handler.popover_copy_link_to_clipboard(instance, $(this));
                    show_copied_confirmation(
                        the($(instance.reference).closest(".message_controls")),
                    );
                })();
            });
        },
        onHidden(instance) {
            const $row = $(instance.reference).closest(".message_row");
            $row.removeClass("has_actions_popover");
            instance.destroy();
            popover_menus.popover_instances.message_actions = null;
            message_actions_popover_keyboard_toggle = false;
        },
    });
}
