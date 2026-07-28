import $ from "jquery";

import render_selection_mode_banner from "../templates/selection_mode_banner.hbs";

import * as banners from "./banners.ts";
import * as channel from "./channel.ts";
import * as compose_actions from "./compose_actions.ts";
import {$t} from "./i18n.ts";
import * as message_lists from "./message_lists.ts";
import * as popovers from "./popovers.ts";
import * as ui_report from "./ui_report.ts";

// Selection mode lets the user pick multiple messages from the
// current view and delete them in one bulk action. The mode is
// entered from the "Delete messages" item in the message-actions
// menu, and is owned by a single message list at a time. Navigating
// to a different view exits the mode without taking any action.

export const UNDO_DELAY_MS = 30_000;

type SelectionState = {
    selected_ids: Set<number>;
    owning_list_id: number | null;
};

const state: SelectionState = {
    selected_ids: new Set(),
    owning_list_id: null,
};

function $banner_container(): JQuery {
    return $("#selection_mode_banner");
}

export function is_active(): boolean {
    return state.owning_list_id !== null;
}

export function selected_count(): number {
    return state.selected_ids.size;
}

export function selected_ids(): number[] {
    return [...state.selected_ids];
}

export function is_selected(message_id: number): boolean {
    return state.selected_ids.has(message_id);
}

function render_banner(): void {
    const count = selected_count();
    // With nothing selected the button is disabled, so we drop the
    // count and show a plain "Delete" rather than "Delete 0 messages".
    const delete_button_text =
        count === 0
            ? $t({defaultMessage: "Delete"})
            : $t(
                  {defaultMessage: "Delete {count, plural, one {# message} other {# messages}}"},
                  {count},
              );
    const html = render_selection_mode_banner({
        delete_button_text,
        cancel_button_text: $t({defaultMessage: "Cancel"}),
        banner_text: $t({
            defaultMessage:
                "Select messages to delete. Deleting messages permanently removes them for everyone.",
        }),
        delete_disabled: count === 0,
    });
    $banner_container().html(html);
    $banner_container().addClass("selection-mode-banner-visible");
}

function clear_dom_state(): void {
    $("body").removeClass("selection-mode-active");
    $banner_container().removeClass("selection-mode-banner-visible").empty();
    $(".message_row.selection-mode-selected").removeClass("selection-mode-selected");
    $(".message_row .message-selection-checkbox").prop("checked", false);
}

export function update_banner(): void {
    if (!is_active()) {
        return;
    }
    render_banner();
}

function update_row_selection_class(message_id: number, selected: boolean): void {
    const $rows = message_lists.all_rendered_row_for_message_id(message_id);
    $rows.toggleClass("selection-mode-selected", selected);
    $rows
        .find(".message-selection-checkbox")
        .prop("checked", selected)
        .attr("aria-checked", selected ? "true" : "false");
}

export function set_selected(message_id: number, selected: boolean): void {
    if (!is_active()) {
        return;
    }
    if (selected) {
        if (state.selected_ids.has(message_id)) {
            return;
        }
        state.selected_ids.add(message_id);
    } else {
        if (!state.selected_ids.has(message_id)) {
            return;
        }
        state.selected_ids.delete(message_id);
    }
    update_row_selection_class(message_id, selected);
    update_banner();
}

export function toggle(message_id: number): void {
    set_selected(message_id, !state.selected_ids.has(message_id));
}

export function enter(initial_message_id: number): void {
    if (message_lists.current === undefined) {
        return;
    }
    state.owning_list_id = message_lists.current.id;
    state.selected_ids = new Set([initial_message_id]);

    popovers.hide_all();
    // Close any open compose box; sending a reply doesn't make sense
    // while picking messages to delete, and leaving it open under a
    // navbar-covering banner would be visually confusing.
    compose_actions.cancel();
    // The `selection-mode-active` body class also deactivates the compose box
    // (see message_selection.css), since composing makes no sense here.
    $("body").addClass("selection-mode-active");
    render_banner();
    update_row_selection_class(initial_message_id, true);
}

export function exit(): void {
    if (!is_active()) {
        return;
    }
    state.selected_ids.clear();
    state.owning_list_id = null;
    clear_dom_state();
}

export function maybe_exit_on_view_change(): void {
    if (!is_active()) {
        return;
    }
    if (message_lists.current?.id !== state.owning_list_id) {
        exit();
    }
}

// Message IDs from the most recently shown undo toast, so its Undo
// button (a delegated handler) knows what to restore. A new deletion
// replaces the banner and hence this list.
let undo_message_ids: number[] = [];

function $undo_banner_container(): JQuery {
    return $("#message_delete_undo_banner");
}

function restore_deleted_messages(): void {
    const message_ids = undo_message_ids;
    undo_message_ids = [];
    $undo_banner_container().empty();
    if (message_ids.length === 0) {
        return;
    }
    // Restore the just-deleted messages from the archive. The server's
    // restored_message events bring them back for everyone who saw them.
    void channel.post({
        url: "/json/messages/restore",
        data: {message_ids: JSON.stringify(message_ids)},
        error(xhr) {
            ui_report.error(
                $t({defaultMessage: "Could not undo; these messages can no longer be restored."}),
                xhr,
                $("#home-error"),
            );
        },
    });
}

function show_undo_toast(message_ids: number[]): void {
    // A success banner with an Undo action, mirroring how deleting
    // drafts is handled in the drafts overlay.
    undo_message_ids = message_ids;
    banners.open_and_close(
        {
            intent: "success",
            label: $t(
                {
                    defaultMessage:
                        "{count, plural, one {# message was deleted.} other {# messages were deleted.}}",
                },
                {count: message_ids.length},
            ),
            buttons: [
                {
                    variant: "subtle",
                    intent: "success",
                    label: $t({defaultMessage: "Undo"}),
                    custom_classes: "message-delete-undo-button",
                },
            ],
            close_button: true,
        },
        $undo_banner_container(),
        UNDO_DELAY_MS,
    );
}

export function confirm_delete(): void {
    if (!is_active()) {
        return;
    }
    const ids_to_delete = selected_ids();
    if (ids_to_delete.length === 0) {
        return;
    }

    exit();

    // Delete immediately for everyone; the server's delete_message events
    // remove the messages from all views, including ours. We then offer an
    // undo that restores them, rather than deferring the deletion, so the
    // messages are never left half-deleted (gone for us but visible to others).
    void channel.del({
        url: "/json/messages",
        data: {message_ids: JSON.stringify(ids_to_delete)},
        success() {
            show_undo_toast(ids_to_delete);
        },
        error(xhr) {
            ui_report.error(
                $t({defaultMessage: "Failed to delete the selected messages."}),
                xhr,
                $("#home-error"),
            );
        },
    });
}

export function initialize(): void {
    // Banner buttons live in the navbar overlay, not inside a
    // message list, so we bind delegated handlers at document scope.
    $("body").on("click", "#selection_mode_banner .selection-mode-delete-button", (e) => {
        e.preventDefault();
        confirm_delete();
    });
    $("body").on("click", "#selection_mode_banner .selection-mode-cancel-button", (e) => {
        e.preventDefault();
        exit();
    });

    // The banner's close button is handled by banners.ts; here we only
    // wire the Undo action, which restores the just-deleted messages.
    $("body").on("click", "#message_delete_undo_banner .message-delete-undo-button", (e) => {
        e.preventDefault();
        restore_deleted_messages();
    });

    // Use `change` rather than `click`: the browser's native
    // checkbox toggle runs before any handlers we attach at body
    // level, so by the time we react `.checked` already reflects
    // the new visual state. We sync our internal selection to that
    // (rather than computing our own diff), to avoid drifting from
    // the DOM if something gets out of step.
    $("body").on(
        "change",
        ".message-selection-checkbox",
        function (this: HTMLInputElement, _e: JQuery.Event) {
            if (!is_active()) {
                return;
            }
            const $row = $(this).closest(".message_row");
            const message_id_attr = $row.attr("data-message-id");
            if (message_id_attr === undefined) {
                return;
            }
            set_selected(Number(message_id_attr), this.checked);
        },
    );
    $("body").on("click", ".message-selection-checkbox-wrapper", (e) => {
        // Swallow the click so it doesn't bubble up to the
        // message-list row click handlers (which would, e.g., open
        // a popover or select that row in the message list).
        e.stopPropagation();
    });
}
