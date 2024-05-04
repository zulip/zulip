import ClipboardJS from "clipboard";
import $ from "jquery";
import assert from "minimalistic-assert";

import render_actions_popover from "../templates/popovers/actions_popover.hbs";

import * as blueslip from "./blueslip";
import * as compose_reply from "./compose_reply";
import * as condense from "./condense";
import {show_copied_confirmation} from "./copied_tooltip";
import * as emoji_picker from "./emoji_picker";
import * as message_edit from "./message_edit";
import * as message_lists from "./message_lists";
import * as message_viewport from "./message_viewport";
import * as popover_menus from "./popover_menus";
import * as popover_menus_data from "./popover_menus_data";
import * as popovers from "./popovers";
import * as read_receipts from "./read_receipts";
import * as rows from "./rows";
import * as stream_popover from "./stream_popover";
import {parse_html} from "./ui_util";
import * as unread_ops from "./unread_ops";

let message_actions_popover_keyboard_toggle = false;

function get_action_menu_menu_items() {
    const $current_actions_popover_elem = $("[data-tippy-root] #message-actions-menu-dropdown");
    if (!$current_actions_popover_elem) {
        blueslip.error("Trying to get menu items when action popover is closed.");
        return undefined;
    }

    return $current_actions_popover_elem.find("li:not(.divider):visible a");
}

function focus_first_action_popover_item() {
    // For now I recommend only calling this when the user opens the menu with a hotkey.
    // Our popup menus act kind of funny when you mix keyboard and mouse.
    const $items = get_action_menu_menu_items();
    popover_menus.focus_first_popover_item($items);
}

export function toggle_message_actions_menu(message) {
    if (popover_menus.is_message_actions_popover_displayed()) {
        popovers.hide_all();
        return true;
    }

    if (message.locally_echoed || message_edit.is_editing(message.id)) {
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
    $popover_reference.trigger("click");
    return true;
}

export function initialize() {
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
            const args = popover_menus_data.get_actions_popover_content_context(message_id);
            instance.setContent(parse_html(render_actions_popover(args)));
            $row.addClass("has_actions_popover");
        },
        onMount(instance) {
            const $row = $(instance.reference).closest(".message_row");
            const message_id = rows.id($row);
            let quote_content;
            if (compose_reply.selection_within_message_id() === message_id) {
                // If the user has selected text within this message, quote only that.
                // We track the selection right now, before the popover option for Quote
                // and reply is clicked, since by then the selection is lost, due to the
                // change in focus.
                quote_content = compose_reply.get_message_selection();
            }
            if (message_actions_popover_keyboard_toggle) {
                focus_first_action_popover_item();
                message_actions_popover_keyboard_toggle = false;
            }
            popover_menus.popover_instances.message_actions = instance;

            // We want click events to propagate to `instance` so that
            // instance.hide gets called.
            const $popper = $(instance.popper);
            $popper.one("click", ".respond_button", (e) => {
                compose_reply.quote_and_reply({
                    trigger: "popover respond",
                    message_id,
                    quote_content,
                });
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

            $popper.one("click", ".popover_move_message", (e) => {
                const message_id = Number($(e.currentTarget).attr("data-message-id"));
                assert(message_lists.current !== undefined);
                message_lists.current.select_id(message_id);
                const message = message_lists.current.get(message_id);
                stream_popover.build_move_topic_to_stream_popover(
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
                if (message.collapsed) {
                    condense.uncollapse(message);
                } else {
                    condense.collapse(message);
                }
                e.preventDefault();
                e.stopPropagation();
                popover_menus.hide_current_popover_if_visible(instance);
            });

            $popper.one("click", ".rehide_muted_user_message", (e) => {
                const message_id = Number($(e.currentTarget).attr("data-message-id"));
                assert(message_lists.current !== undefined);
                const $row = message_lists.current.get_row(message_id);
                const message = message_lists.current.get(rows.id($row));
                const message_container = message_lists.current.view.message_containers.get(
                    message.id,
                );
                if ($row && !message_container.is_hidden) {
                    message_lists.current.view.hide_revealed_message(message_id);
                }
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
                message_edit.delete_message(message_id);
                e.preventDefault();
                e.stopPropagation();
                popover_menus.hide_current_popover_if_visible(instance);
            });

            $popper.one("click", ".reaction_button", (e) => {
                const message_id = Number($(e.currentTarget).attr("data-message-id"));
                // Don't propagate the click event since `toggle_emoji_popover` opens a
                // emoji_picker which we don't want to hide after actions popover is hidden.
                e.stopPropagation();
                e.preventDefault();
                emoji_picker.toggle_emoji_popover(instance.reference.parentElement, message_id, {
                    placement: "bottom",
                });
                popover_menus.hide_current_popover_if_visible(instance);
            });

            new ClipboardJS($popper.find(".copy_link")[0]).on("success", () => {
                show_copied_confirmation($(instance.reference).closest(".message_controls")[0]);
                setTimeout(() => {
                    // The Clipboard library works by focusing to a hidden textarea.
                    // We unfocus this so keyboard shortcuts, etc., will work again.
                    $(":focus").trigger("blur");
                }, 0);
                popover_menus.hide_current_popover_if_visible(instance);
            });
        },
        onHidden(instance) {
            const $row = $(instance.reference).closest(".message_row");
            $row.removeClass("has_actions_popover");
            instance.destroy();
            popover_menus.popover_instances.message_actions = undefined;
            message_actions_popover_keyboard_toggle = false;
        },
    });
}
