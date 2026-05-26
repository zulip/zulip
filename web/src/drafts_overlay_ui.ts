import ClipboardJS from "clipboard";
import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import render_banner from "../templates/components/banner.hbs";
import render_draft_table_body from "../templates/draft_table_body.hbs";
import render_drafts_list from "../templates/drafts_list.hbs";
import render_outbox_list from "../templates/outbox_list.hbs";

import * as browser_history from "./browser_history.ts";
import * as channel from "./channel.ts";
import * as components from "./components.ts";
import * as compose_actions from "./compose_actions.ts";
import {show_copied_confirmation} from "./copied_tooltip.ts";
import type {FormattedDraft, LocalStorageDraft} from "./drafts.ts";
import * as drafts from "./drafts.ts";
import * as echo from "./echo.ts";
import {$t} from "./i18n.ts";
import * as markdown from "./markdown.ts";
import {message_render_response_schema} from "./message_store.ts";
import * as message_view from "./message_view.ts";
import * as messages_overlay_ui from "./messages_overlay_ui.ts";
import * as mouse_drag from "./mouse_drag.ts";
import * as overlays from "./overlays.ts";
import * as people from "./people.ts";
import {postprocess_content} from "./postprocess_content.ts";
import * as rendered_markdown from "./rendered_markdown.ts";
import * as stream_data from "./stream_data.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as user_card_popover from "./user_card_popover.ts";
import * as user_group_popover from "./user_group_popover.ts";

type DraftTab = "drafts" | "outbox";
let current_tab: DraftTab = "drafts";

let draft_undo_delete_list: LocalStorageDraft[] = [];

// Server-rendered HTML keyed by raw_content; lets previews/embeds
// survive rerenders without re-fetching. Cleared on overlay close.
const server_rendered_cache = new Map<string, string>();

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
                variant: "subtle",
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
            message_view.show(
                [{operator: "dm", operand: compose_args.private_message_recipient_ids}],
                {
                    trigger: "restore draft",
                },
            );
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

    if ($(".drafts-tab-pane .overlay-message-row").length === 0) {
        $(".no-drafts").show();
    }
    update_rendered_drafts(
        $(".drafts-tab-pane #drafts-from-conversation .overlay-message-row").length > 0,
        $(".drafts-tab-pane #other-drafts .overlay-message-row").length > 0,
    );
}

function cancel_outbox_messages($outbox_rows: JQuery): void {
    // Cancellation is an intentional discard, so no undo list. The batched
    // echo helper triggers exactly one rerender via the draft-update listener.
    const draft_ids: string[] = [];
    $outbox_rows.each(function () {
        const draft_id = $(this).attr("data-draft-id")!;
        draft_ids.push(draft_id);
    });
    if (draft_ids.length === 0) {
        return;
    }
    echo.abort_messages_by_draft_ids(draft_ids);
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
        const container = current_tab === "outbox" ? ".outbox-tab-pane" : ".drafts-tab-pane";
        const draft_ids: string[] = [];
        for (const row of document.querySelectorAll<HTMLElement>(
            `#drafts_table ${container} .overlay-message-row`,
        )) {
            const id = row.dataset["draftId"];
            assert(id !== undefined);
            draft_ids.push(id);
        }
        return draft_ids;
    },
    on_enter() {
        const draft_id_arrow = this.get_items_ids();
        if (draft_id_arrow.length === 0) {
            return;
        }
        const draft_id = messages_overlay_ui.get_focused_element_id(this) ?? draft_id_arrow.at(0);
        assert(draft_id !== undefined);
        if (current_tab === "outbox") {
            messages_overlay_ui.focus_on_sibling_element(this);
            echo.resend_message_by_draft_id(draft_id);
        } else {
            restore_draft(draft_id);
        }
    },
    on_delete() {
        const focused_element_id = messages_overlay_ui.get_focused_element_id(this);
        if (focused_element_id === undefined) {
            return;
        }
        const $focused_row = messages_overlay_ui.row_with_focus(this);
        messages_overlay_ui.focus_on_sibling_element(this);
        if (current_tab === "outbox") {
            cancel_outbox_messages($focused_row);
        } else {
            remove_drafts($focused_row);
        }
    },
    items_container_selector: "drafts-container",
    get items_list_selector(): string {
        return current_tab === "outbox" ? "outbox-list" : "drafts-list";
    },
    row_item_selector: "draft-message-row",
    box_item_selector: "draft-message-info-box",
    id_attribute_name: "data-draft-id",
};

export function handle_keyboard_events(event_key: string): void {
    messages_overlay_ui.modals_handle_events(event_key, keyboard_handling_context);
}

function format_drafts(data: Record<string, LocalStorageDraft>): FormattedDraft[] {
    const sorted_raw_drafts = Object.entries(data).map(([id, draft]) => ({...draft, id}));
    sorted_raw_drafts.sort((draft_a, draft_b) => draft_b.updatedAt - draft_a.updatedAt);

    const sorted_formatted_drafts = sorted_raw_drafts
        .map((draft_row) => drafts.format_draft(draft_row))
        .filter((formatted_draft) => formatted_draft !== undefined);

    return sorted_formatted_drafts;
}

type NarrowDraftsHeaderContext = {
    is_dm_with_self?: boolean;
    dm_recipient_string?: string;
    stream?: StreamSubscription | undefined;
    channel_name_fallback?: string | undefined;
    topic?: string | undefined;
};

function get_header_context_for_narrow_drafts(): NarrowDraftsHeaderContext {
    const {stream_name, topic, private_recipient_ids} = drafts.current_recipient_data();
    if (private_recipient_ids && private_recipient_ids.length > 0) {
        if (private_recipient_ids.length === 1) {
            const user = people.get_by_user_id(private_recipient_ids[0]!);
            if (user && people.is_direct_message_conversation_with_self([user.user_id])) {
                return {is_dm_with_self: true};
            }
        }
        return {
            dm_recipient_string: people.user_ids_to_full_names_string(private_recipient_ids),
        };
    }
    const stream = stream_name ? stream_data.get_sub_by_name(stream_name) : undefined;
    return {
        stream,
        channel_name_fallback: stream_name,
        topic,
    };
}

function get_formatted_drafts_data(): {
    narrow_drafts: FormattedDraft[];
    other_drafts: FormattedDraft[];
    narrow_drafts_header: NarrowDraftsHeaderContext;
    outbox_drafts: FormattedDraft[];
} {
    const all_drafts = drafts.draft_model.get();
    const outbox_raw: Record<string, LocalStorageDraft> = {};
    const regular_raw: Record<string, LocalStorageDraft> = {};
    for (const [id, draft] of Object.entries(all_drafts)) {
        if (!draft.is_sending_saving) {
            regular_raw[id] = draft;
            continue;
        }
        const echo_status = echo.get_local_echo_status_for_draft(id);
        if (echo_status === "failed") {
            outbox_raw[id] = draft;
        } else if (echo_status === "none") {
            regular_raw[id] = {...draft, is_sending_saving: false};
        }
        // "in_flight" falls through: the message is mid-send (normal
        // transient state) and is visible in the message feed as a local
        // echo, so we don't surface it in either overlay tab.
    }

    const narrow_drafts_raw = drafts.filter_drafts_by_compose_box_and_recipient(regular_raw);
    const other_drafts_raw = _.pick(
        regular_raw,
        _.difference(Object.keys(regular_raw), Object.keys(narrow_drafts_raw)),
    );
    const narrow_drafts = format_drafts(narrow_drafts_raw);
    const other_drafts = format_drafts(other_drafts_raw);
    const outbox_drafts = format_drafts(outbox_raw);
    const narrow_drafts_header = get_header_context_for_narrow_drafts();
    return {narrow_drafts, other_drafts, narrow_drafts_header, outbox_drafts};
}

function render_tab_switcher(draft_count: number, outbox_count: number): void {
    const $container = $("#draft-overlay-tab-switcher");
    $container.empty();

    if (outbox_count === 0) {
        return;
    }

    const toggler = components.toggle({
        html_class: "draft-overlay-tab-switcher",
        values: [
            {
                label: $t({defaultMessage: "Drafts ({draft_count})"}, {draft_count}),
                key: "drafts",
            },
            {
                label: $t({defaultMessage: "Outbox ({outbox_count})"}, {outbox_count}),
                key: "outbox",
            },
        ],
        callback(_label, key) {
            if (key === "drafts" || key === "outbox") {
                current_tab = key;
            }
            update_tab_visibility();
        },
        selected: current_tab === "outbox" ? 1 : 0,
    });

    const $toggler_component = toggler.get();
    $container.append($toggler_component);
}

function update_tab_visibility(): void {
    if (current_tab === "drafts") {
        $(".drafts-tab-pane").show();
        $(".outbox-tab-pane").hide();
        $(".delete-drafts-group").show();
        $(".outbox-actions-group").hide();
        $(".drafts-instruction-note").show();
        $(".outbox-instruction-note").hide();
    } else {
        $(".drafts-tab-pane").hide();
        $(".outbox-tab-pane").show();
        $(".delete-drafts-group").hide();
        $(".outbox-actions-group").show();
        $(".drafts-instruction-note").hide();
        $(".outbox-instruction-note").show();
    }
}

function apply_server_rendered_html(draft_id: string, rendered: string): void {
    const $content_element = $(`[data-draft-id="${CSS.escape(draft_id)}"] .message_content`);
    if ($content_element.length === 0) {
        return;
    }
    $content_element.html(postprocess_content(rendered));
    rendered_markdown.update_elements($content_element);
}

function fetch_server_rendered_drafts(formatted_drafts: FormattedDraft[]): void {
    // compose_ui.ts does thumbnail polling to check for thumbnails for recently
    // uploaded images. We don't want to do that here since there will always
    // be some time delta between writing a message and seeing the draft overlay
    // for it.
    for (const draft of formatted_drafts) {
        if (!markdown.contains_backend_only_syntax(draft.raw_content)) {
            continue;
        }
        const cached = server_rendered_cache.get(draft.raw_content);
        if (cached !== undefined) {
            // Re-apply remembered HTML so previews/embeds survive a rerender
            // without a server round trip.
            apply_server_rendered_html(draft.draft_id, cached);
            continue;
        }
        void channel.post({
            url: "/json/messages/render",
            data: {content: draft.raw_content},
            success(response_data) {
                if (!overlays.drafts_open()) {
                    return;
                }
                const data = message_render_response_schema.parse(response_data);
                server_rendered_cache.set(draft.raw_content, data.rendered);
                apply_server_rendered_html(draft.draft_id, data.rendered);
            },
            // We don't do anything on error and keep displaying the
            // locally rendered message.
        });
    }
}

function render_widgets(
    narrow_drafts: FormattedDraft[],
    other_drafts: FormattedDraft[],
    narrow_drafts_header: NarrowDraftsHeaderContext,
    outbox_drafts: FormattedDraft[],
): void {
    const $drafts_table = $("#drafts_table");
    const is_first_render = $(".drafts-list").length === 0;
    if (is_first_render) {
        const rendered = render_draft_table_body({
            context: {
                narrow_drafts_header,
                narrow_drafts,
                other_drafts,
                outbox_drafts,
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
        const rendered_outbox = render_outbox_list({outbox_drafts});
        $(".outbox-list").replaceWith($(rendered_outbox));
    }
    const draft_count = narrow_drafts.length + other_drafts.length;
    render_tab_switcher(draft_count, outbox_drafts.length);
    update_tab_visibility();
    if ($(".drafts-tab-pane .overlay-message-row").length > 0) {
        $(".no-drafts").hide();
        // .restore-overlay-message is only on regular drafts (see draft.hbs).
        const $rendered_drafts = $drafts_table.find(
            ".message_content.rendered_markdown.restore-overlay-message",
        );
        $rendered_drafts.each(function () {
            rendered_markdown.update_elements($(this));
        });
    }
    if ($(".outbox-tab-pane .overlay-message-row").length > 0) {
        $(".no-outbox-messages").hide();
        // Update possible dynamic elements.
        $drafts_table.find(".outbox-tab-pane .message_content.rendered_markdown").each(function () {
            rendered_markdown.update_elements($(this));
        });
    } else {
        $(".no-outbox-messages").show();
    }
    update_rendered_drafts(narrow_drafts.length > 0, other_drafts.length > 0);
    update_bulk_delete_ui();
    update_bulk_outbox_ui();
    // Re-runs on every render; cache hits avoid the network round trip.
    fetch_server_rendered_drafts([...narrow_drafts, ...other_drafts]);
}

function setup_event_handlers(): void {
    $("#drafts_table .restore-overlay-message").on("click", function (e) {
        if (mouse_drag.is_drag(e)) {
            return;
        }

        if (
            messages_overlay_ui.handle_overlay_media_click(
                e,
                "drafts",
                keyboard_handling_context,
                () => {
                    browser_history.go_to_location("#drafts");
                },
            )
        ) {
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
            // We stop the event from propagating because that is what
            // the main `.messagebox .user-group-mention` click handler
            // expects us to do for drafts.
            e.stopPropagation();
            if (mouse_drag.is_drag(e)) {
                return;
            }

            user_group_popover.toggle_user_group_info_popover(this, undefined);
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

    $("#drafts_table .outbox-resend-message").on("click", function (e) {
        e.stopPropagation();
        const $row = $(this).closest(".overlay-message-row");
        const draft_id = $row.attr("data-draft-id")!;
        echo.resend_message_by_draft_id(draft_id);
    });

    $("#drafts_table .outbox-cancel-message").on("click", function (e) {
        e.stopPropagation();
        const $row = $(this).closest(".overlay-message-row");
        cancel_outbox_messages($row);
    });

    $("#drafts_table .outbox-selection-checkbox").on("click", (e) => {
        const is_checked = is_checkbox_icon_checked($(e.target));
        toggle_checkbox_icon_state($(e.target), !is_checked);
        update_bulk_outbox_ui();
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

    $(".select-outbox-button").on("click", (e) => {
        e.preventDefault();
        const $unchecked = $(".outbox-selection-checkbox").filter(function () {
            return !is_checkbox_icon_checked($(this));
        });
        const check_all = $unchecked.length > 0;
        $(".outbox-selection-checkbox").each(function () {
            toggle_checkbox_icon_state($(this), check_all);
        });
        update_bulk_outbox_ui();
    });

    $(".resend-selected-outbox-button").on("click", function () {
        const $btn = $(this);
        if ($btn.is(":disabled")) {
            return;
        }
        // Disable during the synchronous loop to suppress duplicate clicks.
        $btn.prop("disabled", true);
        // Collect ids first so DOM removals don't affect iteration.
        const draft_ids: string[] = [];
        $(".outbox-list")
            .find(".outbox-selection-checkbox.fa-check-square")
            .closest(".overlay-message-row")
            .each(function () {
                draft_ids.push($(this).attr("data-draft-id")!);
            });
        for (const draft_id of draft_ids) {
            echo.resend_message_by_draft_id(draft_id);
        }
        // Re-enable so the user can retry if the resends fail. Successful
        // resends remove their checkboxes on the next rerender.
        update_bulk_outbox_ui();
    });

    $(".cancel-selected-outbox-button").on("click", () => {
        const $selected_rows = $(".outbox-list")
            .find(".outbox-selection-checkbox.fa-check-square")
            .closest(".overlay-message-row");
        cancel_outbox_messages($selected_rows);
    });
}

function update_bulk_action_ui({
    checkbox_selector,
    select_button_selector,
    action_button_selectors,
}: {
    checkbox_selector: string;
    select_button_selector: string;
    action_button_selectors: string[];
}): void {
    const $checkboxes = $(checkbox_selector);
    const $checked = $checkboxes.filter(function () {
        return is_checkbox_icon_checked($(this));
    });
    const $unchecked = $checkboxes.filter(function () {
        return !is_checkbox_icon_checked($(this));
    });
    const $select_button = $(select_button_selector);
    const $select_indicator = $(`${select_button_selector} .select-state-indicator`);
    const $action_buttons = $(action_button_selectors.join(","));

    if ($checked.length > 0) {
        $action_buttons.prop("disabled", false);
        toggle_checkbox_icon_state($select_indicator, $unchecked.length === 0);
    } else if ($unchecked.length > 0) {
        $select_button.show();
        $action_buttons.show().prop("disabled", true);
        toggle_checkbox_icon_state($select_indicator, false);
    } else {
        $select_button.hide();
        $action_buttons.hide();
    }
}

export function update_bulk_outbox_ui(): void {
    update_bulk_action_ui({
        checkbox_selector: ".outbox-selection-checkbox",
        select_button_selector: ".select-outbox-button",
        action_button_selectors: [
            ".resend-selected-outbox-button",
            ".cancel-selected-outbox-button",
        ],
    });
}

function rerender_drafts(): void {
    const {narrow_drafts, other_drafts, narrow_drafts_header, outbox_drafts} =
        get_formatted_drafts_data();
    if (current_tab === "outbox" && outbox_drafts.length === 0) {
        current_tab = "drafts";
    }
    render_widgets(narrow_drafts, other_drafts, narrow_drafts_header, outbox_drafts);
    setup_event_handlers();
}

export function launch(): void {
    current_tab = "drafts";
    const {narrow_drafts, other_drafts, narrow_drafts_header, outbox_drafts} =
        get_formatted_drafts_data();

    $("#drafts_table").empty();
    render_widgets(narrow_drafts, other_drafts, narrow_drafts_header, outbox_drafts);

    // We need to force a style calculation on the newly created
    // element in order for the CSS transition to take effect.
    $("#draft_overlay").css("opacity");

    open_overlay();
    const restore_id = messages_overlay_ui.get_and_clear_pending_restore_element_id();
    if (
        restore_id === undefined ||
        !messages_overlay_ui.try_set_initial_element(restore_id, keyboard_handling_context)
    ) {
        const first_element_id = [...narrow_drafts, ...other_drafts][0]?.draft_id;
        // Delay focus initialization until the overlay DOM is fully rendered.
        // Otherwise, get_focused_element_id() returns undefined and the focus
        // may not be applied.
        setTimeout(() => {
            messages_overlay_ui.set_initial_element(first_element_id, keyboard_handling_context);
        }, 0);
    }
    setup_event_handlers();
    setup_bulk_actions_handlers();
    drafts.set_draft_update_listener(rerender_drafts);
}

export function update_bulk_delete_ui(): void {
    update_bulk_action_ui({
        checkbox_selector: ".draft-selection-checkbox",
        select_button_selector: ".select-drafts-button",
        action_button_selectors: [".delete-selected-drafts-button"],
    });
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
            drafts.set_draft_update_listener(undefined);
            server_rendered_cache.clear();
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
