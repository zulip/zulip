import ClipboardJS from "clipboard";
import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import render_banner from "../templates/components/banner.hbs";
import render_draft_table_body from "../templates/draft_table_body.hbs";
import render_drafts_list from "../templates/drafts_list.hbs";

import * as browser_history from "./browser_history.ts";
import * as compose_actions from "./compose_actions.ts";
import {show_copied_confirmation} from "./copied_tooltip.ts";
import type {FormattedDraft, LocalStorageDraft} from "./drafts.ts";
import * as drafts from "./drafts.ts";
import {$t} from "./i18n.ts";
import * as message_view from "./message_view.ts";
import * as messages_overlay_ui from "./messages_overlay_ui.ts";
import * as overlays from "./overlays.ts";
import * as people from "./people.ts";
import * as rendered_markdown from "./rendered_markdown.ts";
import * as stream_data from "./stream_data.ts";
import * as user_card_popover from "./user_card_popover.ts";
import * as user_group_popover from "./user_group_popover.ts";

let draft_undo_delete_list: LocalStorageDraft[] = [];

function clear_undo_list(): void {
    draft_undo_delete_list = [];
    $("#draft_overlay_banner_container").empty();
}

function undo_draft_deletion(): void {
    if (draft_undo_delete_list.length === 0) {
        return;
    }

    for (const draft of draft_undo_delete_list) {
        drafts.draft_model.addDraft(draft);
    }

    clear_undo_list();
    rerender_drafts();

    $(".select-drafts-button").show();
    $(".delete-selected-drafts-button").show();
}

function show_delete_banner(): void {
    const $banner_container = $("#draft_overlay_banner_container");
    $banner_container.empty();
    const banner_html = render_banner({
        intent: "success",
        label: $t(
            {
                defaultMessage:
                    "{N, plural, one {# draft was deleted.} other {# drafts were deleted.}}",
            },
            {N: draft_undo_delete_list.length},
        ),
        buttons: [
            {
                attention: "quiet",
                intent: "success",
                label: $t({defaultMessage: "Undo"}),
                custom_classes: "draft-delete-banner-undo-button",
            },
        ],
        close_button: true,
    });

    $banner_container.html(banner_html);
}

function restore_draft(draft_id: string): void {
    const draft = drafts.draft_model.getDraft(draft_id);
    if (!draft) {
        return;
    }

    const compose_args = {...drafts.restore_message(draft), draft_id};

    if (compose_args.type === "stream") {
        if (
            compose_args.stream_id !== undefined &&
            (compose_args.topic !== "" || stream_data.can_use_empty_topic(compose_args.stream_id))
        ) {
            message_view.show(
                [
                    {
                        operator: "channel",
                        operand: compose_args.stream_id.toString(),
                    },
                    {operator: "topic", operand: compose_args.topic},
                ],
                {trigger: "restore draft"},
            );
        }
    } else {
        if (compose_args.private_message_recipient_ids.length > 0) {
            const private_message_recipient_emails =
                people.user_ids_to_emails_string(compose_args.private_message_recipient_ids) ?? "";
            message_view.show([{operator: "dm", operand: private_message_recipient_emails}], {
                trigger: "restore draft",
            });
        }
    }

    overlays.close_overlay("drafts");
    compose_actions.start({
        ...compose_args,
        message_type: compose_args.type,
    });
}

function remove_drafts($draft_rows: JQuery): void {
    // Deletes the drafts and removes it from the list
    const deleted_drafts: LocalStorageDraft[] = [];
    const draft_ids: string[] = [];

    $draft_rows.each(function () {
        const draft_id = $(this).attr("data-draft-id")!;

        const draft = drafts.draft_model.getDraft(draft_id);
        if (draft) {
            deleted_drafts.push(draft);
            draft_ids.push(draft_id);
            $(this).remove();
        }
    });

    if (deleted_drafts.length > 0) {
        drafts.draft_model.deleteDrafts(draft_ids);
        draft_undo_delete_list.push(...deleted_drafts);
        show_delete_banner();
    }

    if ($("#drafts_table .overlay-message-row").length === 0) {
        $("#drafts_table .no-drafts").show();
    }
    update_rendered_drafts(
        $("#drafts-from-conversation .overlay-message-row").length > 0,
        $("#other-drafts .overlay-message-row").length > 0,
    );
}

function update_rendered_drafts(
    has_drafts_from_conversation: boolean,
    has_other_drafts: boolean,
): void {
    if (has_drafts_from_conversation) {
        $("#drafts-from-conversation").show();
    } else {
        // Since there are no relevant drafts from this conversation left, switch to the "all drafts" view and remove headers.
        $("#drafts-from-conversation").hide();
        $("#other-drafts-header").hide();
    }

    if (!has_other_drafts) {
        $("#other-drafts").hide();
    }
}

const keyboard_handling_context: messages_overlay_ui.Context = {
    get_items_ids() {
        const draft_arrow = drafts.draft_model.get();
        return Object.getOwnPropertyNames(draft_arrow);
    },
    on_enter() {
        // This handles when pressing Enter while looking at drafts.
        // It restores draft that is focused.
        const draft_id_arrow = this.get_items_ids();
        const focused_draft_id = messages_overlay_ui.get_focused_element_id(this);
        if (focused_draft_id !== undefined) {
            restore_draft(focused_draft_id);
        } else {
            const first_draft = draft_id_arrow.at(-1);
            assert(first_draft !== undefined);
            restore_draft(first_draft);
        }
    },
    on_delete() {
        // Allows user to delete drafts with Backspace
        const focused_element_id = messages_overlay_ui.get_focused_element_id(this);
        if (focused_element_id === undefined) {
            return;
        }
        const $focused_row = messages_overlay_ui.row_with_focus(this);
        messages_overlay_ui.focus_on_sibling_element(this);
        remove_drafts($focused_row);
    },
    items_container_selector: "drafts-container",
    items_list_selector: "drafts-list",
    row_item_selector: "draft-message-row",
    box_item_selector: "draft-message-info-box",
    id_attribute_name: "data-draft-id",
};

export function handle_keyboard_events(event_key: string): void {
    messages_overlay_ui.modals_handle_events(event_key, keyboard_handling_context);
}

function format_drafts(data: Record<string, LocalStorageDraft>): FormattedDraft[] {
    const unsorted_raw_drafts = Object.entries(data).map(([id, draft]) => ({...draft, id}));

    const sorted_raw_drafts = unsorted_raw_drafts.sort(
        (draft_a, draft_b) => draft_b.updatedAt - draft_a.updatedAt,
    );

    const sorted_formatted_drafts = sorted_raw_drafts
        .map((draft_row) => drafts.format_draft(draft_row))
        .filter((formatted_draft) => formatted_draft !== undefined);

    return sorted_formatted_drafts;
}

function get_header_for_narrow_drafts(): string {
    const {stream_name, topic, private_recipient_ids} = drafts.current_recipient_data();
    if (private_recipient_ids && private_recipient_ids.length > 0) {
        if (private_recipient_ids.length === 1) {
            const user = people.get_by_user_id(private_recipient_ids[0]!);
            if (user && people.is_direct_message_conversation_with_self([user.user_id])) {
                return $t({defaultMessage: "Drafts from conversation with yourself"});
            }
        }
        return $t(
            {defaultMessage: "Drafts from conversation with {recipient}"},
            {
                recipient: people.user_ids_to_full_names_string(private_recipient_ids),
            },
        );
    }
    const recipient = topic ? `#${stream_name} > ${topic}` : `#${stream_name}`;
    return $t({defaultMessage: "Drafts from {recipient}"}, {recipient});
}

function get_formatted_drafts_data(): {
    narrow_drafts: FormattedDraft[];
    other_drafts: FormattedDraft[];
    narrow_drafts_header: string;
} {
    const all_drafts = drafts.draft_model.get();
    const narrow_drafts_raw = drafts.filter_drafts_by_compose_box_and_recipient(all_drafts);
    const other_drafts_raw = _.pick(
        all_drafts,
        _.difference(Object.keys(all_drafts), Object.keys(narrow_drafts_raw)),
    );
    const narrow_drafts = format_drafts(narrow_drafts_raw);
    const other_drafts = format_drafts(other_drafts_raw);
    const narrow_drafts_header = get_header_for_narrow_drafts();
    return {narrow_drafts, other_drafts, narrow_drafts_header};
}

function render_widgets(
    narrow_drafts: FormattedDraft[],
    other_drafts: FormattedDraft[],
    narrow_drafts_header: string,
): void {
    const $drafts_table = $("#drafts_table");
    if ($(".drafts-list").length === 0) {
        const rendered = render_draft_table_body({
            context: {
                narrow_drafts_header,
                narrow_drafts,
                other_drafts,
            },
        });
        $drafts_table.append($(rendered));
    } else {
        const rendered = render_drafts_list({
            narrow_drafts_header,
            narrow_drafts,
            other_drafts,
        });
        $(".drafts-list").replaceWith($(rendered));
    }
    if ($("#drafts_table .overlay-message-row").length > 0) {
        $("#drafts_table .no-drafts").hide();
        // Update possible dynamic elements.
        const $rendered_drafts = $drafts_table.find(
            ".message_content.rendered_markdown.restore-overlay-message",
        );
        $rendered_drafts.each(function () {
            rendered_markdown.update_elements($(this));
        });
    }
    update_rendered_drafts(narrow_drafts.length > 0, other_drafts.length > 0);
    update_bulk_delete_ui();
}

function setup_event_handlers(): void {
    $("#drafts_table .restore-overlay-message").on("click", function (e) {
        if (document.getSelection()?.type === "Range") {
            return;
        }

        e.stopPropagation();

        const $draft_row = $(this).closest(".overlay-message-row");
        const draft_id = $draft_row.attr("data-draft-id")!;
        restore_draft(draft_id);
    });

    $("#drafts_table .restore-overlay-message").on(
        "click",
        ".user-mention",
        user_card_popover.unsaved_message_user_mention_event_handler,
    );

    $("#drafts_table .restore-overlay-message").on(
        "click",
        ".user-group-mention",
        function (this: HTMLElement, e) {
            if (document.getSelection()?.type === "Range") {
                return;
            }

            user_group_popover.toggle_user_group_info_popover(this, undefined);
            e.stopPropagation();
        },
    );

    $("#drafts_table .overlay_message_controls .delete-overlay-message").on("click", function () {
        const $draft_row = $(this).closest(".overlay-message-row");

        remove_drafts($draft_row);
        update_bulk_delete_ui();
    });

    $("#drafts_table .overlay_message_controls .draft-selection-checkbox").on("click", (e) => {
        const is_checked = is_checkbox_icon_checked($(e.target));
        toggle_checkbox_icon_state($(e.target), !is_checked);
        update_bulk_delete_ui();
    });

    new ClipboardJS("#drafts_table .overlay_message_controls .copy-overlay-message", {
        text(trigger): string {
            const draft_id = $(trigger).attr("data-draft-id")!;
            const draft = drafts.draft_model.getDraft(draft_id);
            if (!draft) {
                return "";
            }
            return draft.content ?? "";
        },
    }).on("success", (e) => {
        show_copied_confirmation(e.trigger, {
            show_check_icon: true,
        });
    });
}

function setup_bulk_actions_handlers(): void {
    $(".select-drafts-button").on("click", (e) => {
        e.preventDefault();
        const $unchecked_checkboxes = $(".draft-selection-checkbox").filter(function () {
            return !is_checkbox_icon_checked($(this));
        });
        const check_boxes = $unchecked_checkboxes.length > 0;
        $(".draft-selection-checkbox").each(function () {
            toggle_checkbox_icon_state($(this), check_boxes);
        });
        update_bulk_delete_ui();
    });

    $(".delete-selected-drafts-button").on("click", () => {
        const $selected_rows = $(".drafts-list")
            .find(".draft-selection-checkbox.fa-check-square")
            .closest(".overlay-message-row");
        remove_drafts($selected_rows);
        update_bulk_delete_ui();
    });
}

function rerender_drafts(): void {
    const {narrow_drafts, other_drafts, narrow_drafts_header} = get_formatted_drafts_data();
    render_widgets(narrow_drafts, other_drafts, narrow_drafts_header);
    setup_event_handlers();
}

export function launch(): void {
    const {narrow_drafts, other_drafts, narrow_drafts_header} = get_formatted_drafts_data();

    $("#drafts_table").empty();
    render_widgets(narrow_drafts, other_drafts, narrow_drafts_header);

    // We need to force a style calculation on the newly created
    // element in order for the CSS transition to take effect.
    $("#draft_overlay").css("opacity");

    open_overlay();
    const first_element_id = [...narrow_drafts, ...other_drafts][0]?.draft_id;
    messages_overlay_ui.set_initial_element(first_element_id, keyboard_handling_context);
    setup_event_handlers();
    setup_bulk_actions_handlers();
}

export function update_bulk_delete_ui(): void {
    const $unchecked_checkboxes = $(".draft-selection-checkbox").filter(function () {
        return !is_checkbox_icon_checked($(this));
    });
    const $checked_checkboxes = $(".draft-selection-checkbox").filter(function () {
        return is_checkbox_icon_checked($(this));
    });
    const $select_drafts_button = $(".select-drafts-button");
    const $select_state_indicator = $(".select-drafts-button .select-state-indicator");
    const $delete_selected_drafts_button = $(".delete-selected-drafts-button");

    if ($checked_checkboxes.length > 0) {
        $delete_selected_drafts_button.prop("disabled", false);
        if ($unchecked_checkboxes.length === 0) {
            toggle_checkbox_icon_state($select_state_indicator, true);
        } else {
            toggle_checkbox_icon_state($select_state_indicator, false);
        }
    } else {
        if ($unchecked_checkboxes.length > 0) {
            toggle_checkbox_icon_state($select_state_indicator, false);
            $delete_selected_drafts_button.prop("disabled", true);
        } else {
            $select_drafts_button.hide();
            $delete_selected_drafts_button.hide();
        }
    }
}

export function open_overlay(): void {
    drafts.sync_count();
    overlays.open_overlay({
        name: "drafts",
        $overlay: $("#draft_overlay"),
        on_close() {
            browser_history.exit_overlay();
            drafts.sync_count();
            draft_undo_delete_list = [];
        },
    });
}

export function is_checkbox_icon_checked($checkbox: JQuery): boolean {
    return $checkbox.hasClass("fa-check-square");
}

export function toggle_checkbox_icon_state($checkbox: JQuery, checked: boolean): void {
    $checkbox.parent().attr("aria-checked", checked.toString());
    if (checked) {
        $checkbox.removeClass("fa-square-o").addClass("fa-check-square");
    } else {
        $checkbox.removeClass("fa-check-square").addClass("fa-square-o");
    }
}

export function initialize(): void {
    $("body").on("focus", "#drafts_table .overlay-message-info-box", function (this: HTMLElement) {
        messages_overlay_ui.activate_element(this, keyboard_handling_context);
    });
    $("body").on(
        "click",
        "#draft_overlay_banner_container .draft-delete-banner-undo-button",
        undo_draft_deletion,
    );
    $("body").on("click", "#draft_overlay_banner_container .banner-close-button", clear_undo_list);
}
