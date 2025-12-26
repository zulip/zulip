import ClipboardJS from "clipboard";
import $ from "jquery";
import _ from "lodash";

import render_banner from "../templates/components/banner.hbs";
import render_draft_table_body from "../templates/draft_table_body.hbs";
import render_drafts_list from "../templates/drafts_list.hbs";

import * as browser_history from "./browser_history.ts";
import * as compose_actions from "./compose_actions.ts";
import {show_copied_confirmation} from "./copied_tooltip.ts";
import type {FormattedDraft, LocalStorageDraft} from "./drafts.ts";
import * as drafts from "./drafts.ts";
import * as echo_state from "./echo_state.ts";
import {$t} from "./i18n.ts";
import * as message_view from "./message_view.ts";
import * as messages_overlay_ui from "./messages_overlay_ui.ts";
import * as mouse_drag from "./mouse_drag.ts";
import * as overlays from "./overlays.ts";
import * as people from "./people.ts";
import * as rendered_markdown from "./rendered_markdown.ts";
import * as stream_data from "./stream_data.ts";
import * as user_card_popover from "./user_card_popover.ts";
import * as user_group_popover from "./user_group_popover.ts";
import * as util from "./util.ts";

// --- State ---
let active_tab: "drafts" | "outbox" = "drafts";
let draft_undo_delete_list: LocalStorageDraft[] = [];

// --- Helpers ---

function clear_undo_list(): void {
    draft_undo_delete_list = [];
    $("#draft_overlay_banner_container").empty();
}

function safe_close_overlay(): void {
    if (overlays.drafts_open()) {
        overlays.close_overlay("drafts");
    }
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
    update_bulk_delete_ui();
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
                    {operator: "channel", operand: compose_args.stream_id.toString()},
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

    safe_close_overlay();
    compose_actions.start({...compose_args, message_type: compose_args.type});
}

function remove_drafts($draft_rows: JQuery): void {
    const deleted_drafts: LocalStorageDraft[] = [];
    const draft_ids: string[] = [];

    $draft_rows.each(function (this: HTMLElement) {
        const draft_id = $(this).attr("data-draft-id")!;
        if (!draft_id.startsWith("outbox_")) {
            const draft = drafts.draft_model.getDraft(draft_id);
            if (draft) {
                deleted_drafts.push(draft);
                draft_ids.push(draft_id);
            }
        }
        $(this).remove();
    });

    if (draft_ids.length > 0) {
        drafts.draft_model.deleteDrafts(draft_ids);
        draft_undo_delete_list.push(...deleted_drafts);
        show_delete_banner();
    }

    if (active_tab === "drafts") {
        if ($("#drafts_table .overlay-message-row").length === 0) {
            $("#drafts_table .no-drafts").show();
        }
    } else {
        if ($("#drafts_table .overlay-message-row").length === 0) {
            $("#drafts_table .no-drafts").show();
        }
    }
}

function format_drafts(data: Record<string, LocalStorageDraft>): FormattedDraft[] {
    const sorted_raw_drafts = Object.entries(data).map(([id, draft]) => ({...draft, id}));
    sorted_raw_drafts.sort((draft_a, draft_b) => draft_b.updatedAt - draft_a.updatedAt);
    return sorted_raw_drafts
        .map((draft_row) => drafts.format_draft(draft_row))
        .filter((formatted_draft) => formatted_draft !== undefined);
}

function format_outbox_messages(
    messages: ReturnType<typeof echo_state.get_global_outbox_messages>,
): FormattedDraft[] {
    const sorted_messages = messages.toSorted((a, b) => (b.timestamp ?? 0) - (a.timestamp ?? 0));

    return sorted_messages.map((msg, index): FormattedDraft => {
        const draft_id = `outbox_${index}`;
        const time_str = $t({defaultMessage: "Waiting to send..."});

        // LocalMessage has 'content' property (HTML), we need to strip HTML tags for display
        const html_content = msg.content || "";
        // Create a temporary div to strip HTML tags
        const temp_div = document.createElement("div");
        temp_div.innerHTML = html_content;
        const message_content = temp_div.textContent || "";

        if (msg.type === "stream") {
            let stream_name = "Unknown Stream";
            let stream_id = -1;
            let stream_obj = null;

            if (msg.stream_id !== undefined) {
                stream_id = msg.stream_id;
                stream_obj = stream_data.get_sub_by_id(stream_id);
                if (stream_obj) {
                    stream_name = stream_obj.name;
                }
            }

            const topic = msg.topic ?? "";
            const default_color = "#c2c2c2";
            const color = stream_obj ? stream_data.get_color(stream_obj.stream_id) : default_color;

            return {
                is_stream: true,
                draft_id,
                stream_name,
                stream_id,
                recipient_bar_color: color,
                stream_privacy_icon_color: color,
                topic_display_name: util.get_final_topic_display_name(topic),
                is_empty_string_topic: topic === "",
                invite_only: stream_obj?.invite_only ?? false,
                is_web_public: stream_obj?.is_web_public ?? false,
                content: message_content,
                raw_content: message_content,
                time_stamp: time_str,
            };
        }

        // Handle DMs
        let recipients = "";
        let is_dm_with_self = false;
        let has_recipient_data = false;

        if (Array.isArray(msg.display_recipient)) {
            recipients = msg.display_recipient
                .map((r: {full_name: string}) => r.full_name)
                .join(", ");
            has_recipient_data = true;
            is_dm_with_self =
                msg.display_recipient.length === 1 &&
                msg.display_recipient[0]?.id === msg.sender_id;
        }

        return {
            is_stream: false,
            draft_id,
            recipients,
            is_dm_with_self,
            has_recipient_data,
            content: message_content,
            raw_content: message_content,
            time_stamp: time_str,
        };
    });
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
            {recipient: people.user_ids_to_full_names_string(private_recipient_ids)},
        );
    }
    const recipient = topic ? `#${stream_name} > ${topic}` : `#${stream_name}`;
    if (!stream_name) {
        return $t({defaultMessage: "Drafts"});
    }
    return $t({defaultMessage: "Drafts from {recipient}"}, {recipient});
}

function render_tabs(draft_count: number, outbox_count: number): void {
    const $header_body = $(".drafts-container .header-body");

    $(".drafts-container .tab-switcher-container").remove();

    if (outbox_count === 0) {
        active_tab = "drafts";
        return;
    }

    const draftsClass = active_tab === "drafts" ? "selected" : "";
    const outboxClass = active_tab === "outbox" ? "selected" : "";
    const drafts_border_color = active_tab === "drafts" ? "hsl(240, 96%, 68%)" : "transparent";
    const outbox_border_color = active_tab === "outbox" ? "hsl(240, 96%, 68%)" : "transparent";

    const $tabs = $("<div>").addClass("tab-switcher-container").css({
        margin: "15px 0",
        "text-align": "center",
        "border-bottom": "1px solid hsla(0, 0%, 50%, 0.2)",
    });

    const $tab_switcher = $("<div>").addClass("tab-switcher");

    const $drafts_tab = $("<div>")
        .addClass(`ind-tab ${draftsClass}`)
        .attr({
            "data-tab": "drafts",
            tabindex: "0",
        })
        .css({
            display: "inline-block",
            padding: "8px 20px",
            cursor: "pointer",
            "font-weight": "500",
            "border-bottom": `3px solid ${drafts_border_color}`,
        })
        .text(`${$t({defaultMessage: "Drafts"})} (${draft_count})`);

    const $outbox_tab = $("<div>")
        .addClass(`ind-tab ${outboxClass}`)
        .attr({
            "data-tab": "outbox",
            tabindex: "0",
        })
        .css({
            display: "inline-block",
            padding: "8px 20px",
            cursor: "pointer",
            "font-weight": "500",
            "border-bottom": `3px solid ${outbox_border_color}`,
        })
        .text(`${$t({defaultMessage: "Outbox"})} (${outbox_count})`);

    $tab_switcher.append($drafts_tab, $outbox_tab);
    $tabs.append($tab_switcher);
    $header_body.after($tabs);
}

function render_widgets(): void {
    const all_drafts_raw = drafts.draft_model.get();
    const narrow_drafts_raw = drafts.filter_drafts_by_compose_box_and_recipient(all_drafts_raw);
    const other_drafts_raw = _.pick(
        all_drafts_raw,
        _.difference(Object.keys(all_drafts_raw), Object.keys(narrow_drafts_raw)),
    );

    const narrow_drafts = format_drafts(narrow_drafts_raw);
    const other_drafts = format_drafts(other_drafts_raw);
    const draft_count = narrow_drafts.length + other_drafts.length;

    const outbox_messages = echo_state.get_global_outbox_messages();
    const outbox_count = outbox_messages.length;

    const $drafts_table = $("#drafts_table");

    if ($(".drafts-list").length === 0) {
        const narrow_drafts_header = get_header_for_narrow_drafts();
        const rendered = render_draft_table_body({
            context: {
                narrow_drafts_header,
                narrow_drafts,
                other_drafts,
            },
        });
        $drafts_table.empty().append($(rendered));
    }

    render_tabs(draft_count, outbox_count);

    if (active_tab === "outbox") {
        const formatted_outbox = format_outbox_messages(outbox_messages);

        if (outbox_count === 0) {
            const html = render_drafts_list({
                narrow_drafts_header: $t({defaultMessage: "No messages in outbox."}),
                narrow_drafts: [],
                other_drafts: [],
            });
            $(".drafts-list").replaceWith($(html));
            $(".no-drafts").show();
        } else {
            const html = render_drafts_list({
                narrow_drafts_header: $t({defaultMessage: "Unsent messages"}),
                narrow_drafts: formatted_outbox,
                other_drafts: [],
            });
            $(".drafts-list").replaceWith($(html));

            $(".restore-overlay-message").hide();
            $(".drafts-list .message_content").css("display", "block");
            $(".delete-overlay-message").attr("title", $t({defaultMessage: "Cancel sending"}));
        }
    } else {
        const narrow_drafts_header = get_header_for_narrow_drafts();
        const html = render_drafts_list({
            narrow_drafts_header,
            narrow_drafts,
            other_drafts,
        });
        $(".drafts-list").replaceWith($(html));

        if (draft_count === 0) {
            $(".no-drafts").show();
        } else {
            $(".no-drafts").hide();
        }
    }

    if ($("#drafts_table .overlay-message-row").length > 0) {
        $("#drafts_table .no-drafts").hide();
        const $rendered_drafts = $("#drafts_table").find(".message_content.rendered_markdown");
        $rendered_drafts.each(function (this: HTMLElement) {
            rendered_markdown.update_elements($(this));
        });
    }

    update_bulk_delete_ui();
}

function rerender_drafts(): void {
    render_widgets();
}

function setup_event_handlers(): void {
    $("body")
        .off("click", ".ind-tab")
        .on("click", ".ind-tab", function (this: HTMLElement) {
            const tab = $(this).attr("data-tab");
            if (tab === "drafts" || tab === "outbox") {
                active_tab = tab;
                rerender_drafts();
            }
        });

    const $overlay = $("#draft_overlay");

    $overlay.on("click", ".restore-overlay-message", function (this: HTMLElement, e) {
        if (mouse_drag.is_drag(e)) {
            return;
        }
        e.stopPropagation();
        const draft_id = $(this).closest(".overlay-message-row").attr("data-draft-id")!;
        restore_draft(draft_id);
    });

    $overlay.on("click", ".delete-overlay-message", function (this: HTMLElement) {
        const $draft_row: JQuery = $(this).closest(".overlay-message-row");
        remove_drafts($draft_row);
        update_bulk_delete_ui();
    });

    $overlay.on(
        "click",
        ".user-mention",
        user_card_popover.unsaved_message_user_mention_event_handler,
    );
    $overlay.on("click", ".user-group-mention", function (this: HTMLElement, e) {
        e.stopPropagation();
        if (mouse_drag.is_drag(e)) {
            return;
        }
        user_group_popover.toggle_user_group_info_popover(this, undefined);
    });

    $overlay.on("click", ".draft-selection-checkbox", function (this: HTMLElement) {
        const $this: JQuery = $(this);
        const is_checked = is_checkbox_icon_checked($this);
        toggle_checkbox_icon_state($this, !is_checked);
        update_bulk_delete_ui();
    });

    new ClipboardJS("#draft_overlay .copy-overlay-message", {
        text(trigger): string {
            const draft_id = $(trigger).attr("data-draft-id");
            if (!draft_id) {
                return "";
            }
            if (draft_id.startsWith("outbox_")) {
                const index = Number.parseInt(draft_id.split("_")[1]!, 10);
                const outbox_msgs = echo_state.get_global_outbox_messages();
                const msg = outbox_msgs[index];
                if (!msg) {
                    return "";
                }
                return msg.content || "";
            }
            const draft = drafts.draft_model.getDraft(draft_id);
            return draft ? draft.content : "";
        },
    }).on("success", (e) => {
        show_copied_confirmation(e.trigger, {show_check_icon: true});
    });
}

function setup_bulk_actions_handlers(): void {
    $("body").on("click", "#draft_overlay .select-drafts-button", (e) => {
        e.preventDefault();
        const $unchecked = $(".draft-selection-checkbox").not(".fa-check-square");
        const check_boxes = $unchecked.length > 0;
        $(".draft-selection-checkbox").each(function (this: HTMLElement) {
            const $this: JQuery = $(this);
            toggle_checkbox_icon_state($this, check_boxes);
        });
        update_bulk_delete_ui();
    });

    $("body").on("click", "#draft_overlay .delete-selected-drafts-button", () => {
        const $selected_rows = $("#drafts_table")
            .find(".draft-selection-checkbox.fa-check-square")
            .closest(".overlay-message-row");
        remove_drafts($selected_rows);
        update_bulk_delete_ui();
    });
}

const keyboard_handling_context: messages_overlay_ui.Context = {
    get_items_ids() {
        if (active_tab === "outbox") {
            const msgs = echo_state.get_global_outbox_messages();
            return msgs.map((_, i) => `outbox_${i}`);
        }
        const draft_arrow = drafts.draft_model.get();
        return Object.getOwnPropertyNames(draft_arrow);
    },
    on_enter() {
        const focused_draft_id = messages_overlay_ui.get_focused_element_id(this);
        if (focused_draft_id !== undefined && active_tab === "drafts") {
            restore_draft(focused_draft_id);
        }
    },
    on_delete() {
        const focused_element_id = messages_overlay_ui.get_focused_element_id(this);
        if (focused_element_id === undefined) {
            return;
        }
        const $focused_row: JQuery = messages_overlay_ui.row_with_focus(this);
        messages_overlay_ui.focus_on_sibling_element(this);
        remove_drafts($focused_row);
    },
    items_container_selector: "drafts-container",
    items_list_selector: "drafts-list",
    row_item_selector: "overlay-message-row",
    box_item_selector: "overlay-message-info-box",
    id_attribute_name: "data-draft-id",
};

export function handle_keyboard_events(event_key: string): void {
    messages_overlay_ui.modals_handle_events(event_key, keyboard_handling_context);
}

export function launch(): void {
    active_tab = "drafts";
    clear_undo_list();

    $("#drafts_table").empty();
    render_widgets();

    $("#draft_overlay").css("opacity");

    overlays.open_overlay({
        name: "drafts",
        $overlay: $("#draft_overlay"),
        on_close() {
            browser_history.exit_overlay();
            drafts.sync_count();
            clear_undo_list();
        },
    });

    const all_ids = keyboard_handling_context.get_items_ids();
    if (all_ids.length > 0) {
        messages_overlay_ui.set_initial_element(all_ids[0], keyboard_handling_context);
    }

    setup_event_handlers();
    setup_bulk_actions_handlers();
}

export function update_bulk_delete_ui(): void {
    const $unchecked = $(".draft-selection-checkbox").not(".fa-check-square");
    const $checked = $(".draft-selection-checkbox.fa-check-square");
    const $delete_btn = $(".delete-selected-drafts-button");
    const $state_indicator = $(".select-drafts-button .select-state-indicator");
    const $select_btn = $(".select-drafts-button");

    let label = $t({defaultMessage: "Delete selected"});
    if (active_tab === "outbox") {
        label = $t({defaultMessage: "Cancel selected"});
    }
    $delete_btn.text(label);

    if ($checked.length > 0) {
        $delete_btn.prop("disabled", false);
        toggle_checkbox_icon_state($state_indicator, $unchecked.length === 0);
    } else {
        if ($unchecked.length > 0) {
            toggle_checkbox_icon_state($state_indicator, false);
            $delete_btn.prop("disabled", true);
        } else {
            $select_btn.hide();
            $delete_btn.hide();
        }
    }
}

export function open_overlay(): void {
    launch();
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

    setup_event_handlers();
    setup_bulk_actions_handlers();
}
