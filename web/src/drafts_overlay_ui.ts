import ClipboardJS from "clipboard";
import {$} from "jquery";
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
import * as overlay_util from "./overlay_util.ts";
import * as overlays from "./overlays.ts";
import * as people from "./people.ts";
import {postprocess_content} from "./postprocess_content.ts";
import * as rendered_markdown from "./rendered_markdown.ts";
import * as scroll_util from "./scroll_util.ts";
import * as stream_data from "./stream_data.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as user_card_popover from "./user_card_popover.ts";
import * as user_group_popover from "./user_group_popover.ts";

let current_tab: "drafts" | "outbox" = "drafts";

// The banner can only describe one kind of discard, so a different kind
// starts a new batch.
let draft_undo_list: LocalStorageDraft[] = [];
let draft_undo_action: "delete" | "cancel" | undefined;

// Server-rendered HTML keyed by raw_content; lets previews/embeds survive
// rerenders without re-fetching, so that when rerenders replace the list DOM,
// the previews don't flicker out and back in. Cleared on overlay close.
const server_rendered_cache = new Map<string, string>();

let rendered_outbox_count = 0;

function clear_undo_list(): void {
    draft_undo_list = [];
    draft_undo_action = undefined;
    $("#draft_overlay_banner_container").empty();
}

function undo_discarded_drafts(): void {
    if (draft_undo_list.length === 0) {
        return;
    }

    // `addDraft` is where the rerender happens (via draft_rerender_listener),
    // and we make sure to only rerender on the last entry so that we only
    // rerender once rather than N times.
    const last_index = draft_undo_list.length - 1;
    for (const [index, draft] of draft_undo_list.entries()) {
        drafts.draft_model.addDraft(draft, index === last_index);
    }

    clear_undo_list();

    $(".select-drafts-button").show();
    $(".delete-selected-drafts-button").show();
}

function offer_undo(discarded_drafts: LocalStorageDraft[], action: "delete" | "cancel"): void {
    if (action !== draft_undo_action) {
        draft_undo_list = [];
        draft_undo_action = action;
    }
    draft_undo_list.push(...discarded_drafts);

    const $banner_container = $("#draft_overlay_banner_container");
    $banner_container.empty();
    const banner_html = render_banner({
        intent: "success",
        label:
            action === "delete"
                ? $t(
                      {
                          defaultMessage:
                              "{N, plural, one {# draft was deleted.} other {# drafts were deleted.}}",
                      },
                      {N: draft_undo_list.length},
                  )
                : $t(
                      {
                          defaultMessage:
                              "{N, plural, one {# message was canceled.} other {# messages were canceled.}}",
                      },
                      {N: draft_undo_list.length},
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
        offer_undo(deleted_drafts, "delete");
    }

    if ($(".drafts-tab-pane .overlay-message-row").length === 0) {
        $(".drafts-tab-pane .no-drafts").show();
    }
    update_rendered_drafts(
        $("#drafts-from-conversation .overlay-message-row").length > 0,
        $("#other-drafts .overlay-message-row").length > 0,
    );
}

function cancel_outbox_messages($outbox_rows: JQuery): void {
    const draft_ids: string[] = [];
    const canceled_drafts: LocalStorageDraft[] = [];
    $outbox_rows.each(function () {
        const draft_id = $(this).attr("data-draft-id")!;
        draft_ids.push(draft_id);
        const draft = drafts.draft_model.getDraft(draft_id);
        if (draft) {
            // Canceling destroys the local echo, so undo can only bring
            // the text back as an ordinary draft.
            canceled_drafts.push({...draft, is_sending_saving: false});
        }
    });
    if (draft_ids.length === 0) {
        return;
    }
    echo.abort_messages_by_draft_ids(draft_ids);
    if (canceled_drafts.length > 0) {
        offer_undo(canceled_drafts, "cancel");
    }
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
        $(`${container} .overlay-message-row`).each(function () {
            const id = $(this).attr("data-draft-id");
            assert(id !== undefined);
            draft_ids.push(id);
        });
        return draft_ids;
    },
    on_enter() {
        const draft_id_arrow = this.get_items_ids();
        if (draft_id_arrow.length === 0) {
            return;
        }
        const focused_draft_id = messages_overlay_ui.get_focused_element_id(this);
        if (current_tab === "outbox") {
            // Resending actually sends, so never fall back to the first row.
            if (focused_draft_id === undefined) {
                return;
            }
            messages_overlay_ui.focus_on_sibling_element(this);
            echo.resend_message_by_draft_id(focused_draft_id);
            return;
        }
        const draft_id = focused_draft_id ?? draft_id_arrow.at(0);
        assert(draft_id !== undefined);
        restore_draft(draft_id);
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
            // A send that isn't locally echoed, including a scheduled one,
            // holds the flag until it resolves.
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
            assert(key === "drafts" || key === "outbox");
            current_tab = key;
            update_tab_visibility();
        },
        selected: current_tab === "outbox" ? 1 : 0,
    });

    const $toggler_component = toggler.get();
    $container.append($toggler_component);
}

function update_tab_visibility(): void {
    $("#draft_overlay .draft-overlay-tab-section").hide();
    $(`#draft_overlay [data-tab-section="${CSS.escape(current_tab)}"]`).show();
}

function focus_first_row_of_current_tab(): void {
    messages_overlay_ui.set_initial_element(
        keyboard_handling_context.get_items_ids().at(0),
        keyboard_handling_context,
    );
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

// Update possible dynamic elements.
function update_rendered_markdown_in(pane_selector: string): void {
    $("#drafts_table")
        .find(`${pane_selector} .message_content.rendered_markdown`)
        .each(function () {
            rendered_markdown.update_elements($(this));
        });
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
        const rendered_regular_drafts = render_drafts_list({
            narrow_drafts_header,
            narrow_drafts,
            other_drafts,
        });
        $(".drafts-list").replaceWith($(rendered_regular_drafts));
        const rendered_outbox = render_outbox_list({outbox_drafts});
        $(".outbox-list").replaceWith($(rendered_outbox));
    }
    const draft_count = narrow_drafts.length + other_drafts.length;
    render_tab_switcher(draft_count, outbox_drafts.length);
    update_tab_visibility();
    if ($(".drafts-tab-pane .overlay-message-row").length > 0) {
        $(".drafts-tab-pane .no-drafts").hide();
        update_rendered_markdown_in(".drafts-tab-pane");
    }
    // The Outbox pane is only ever shown non-empty, so it has no empty state.
    if ($(".outbox-tab-pane .overlay-message-row").length > 0) {
        update_rendered_markdown_in(".outbox-tab-pane");
    }
    update_rendered_drafts(narrow_drafts.length > 0, other_drafts.length > 0);
    rendered_outbox_count = outbox_drafts.length;
    update_bulk_delete_ui();
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

type OverlayTransientState = {
    checked_draft_ids: Set<string>;
    focused_draft_id: string | undefined;
    scroll_tops: Map<string, number>;
};

// A rerender replaces the whole list DOM, so capture the state it discards.
function capture_overlay_state(): OverlayTransientState {
    const checked_draft_ids = new Set<string>();
    $("#drafts_table .overlay-message-row").each(function () {
        const draft_id = $(this).attr("data-draft-id");
        const $checkbox = $(this).find(".draft-selection-checkbox");
        if (draft_id !== undefined && is_checkbox_icon_checked($checkbox)) {
            checked_draft_ids.add(draft_id);
        }
    });

    const scroll_tops = new Map<string, number>();
    for (const selector of [".drafts-list", ".outbox-list"]) {
        const $list = $(selector);
        if ($list.length > 0) {
            scroll_tops.set(selector, scroll_util.get_scroll_element($list).scrollTop() ?? 0);
        }
    }

    return {
        checked_draft_ids,
        focused_draft_id: messages_overlay_ui.get_focused_element_id(keyboard_handling_context),
        scroll_tops,
    };
}

function restore_overlay_state({
    checked_draft_ids,
    focused_draft_id,
    scroll_tops,
}: OverlayTransientState): void {
    if (checked_draft_ids.size > 0) {
        $("#drafts_table .overlay-message-row").each(function () {
            const draft_id = $(this).attr("data-draft-id");
            if (draft_id !== undefined && checked_draft_ids.has(draft_id)) {
                toggle_checkbox_icon_state($(this).find(".draft-selection-checkbox"), true);
            }
        });
        // Re-run now that the checkboxes are restored; render_widgets ran
        // these against the empty pre-restore selection.
        update_bulk_delete_ui();
    }

    // Deferred because focusing right after the DOM swap lands on <body>.
    // Scroll goes after focus, which would otherwise scroll its row into view.
    setTimeout(() => {
        if (!overlays.drafts_open()) {
            // The rows outlive the overlay, so this could act on a closed one.
            return;
        }
        if (focused_draft_id !== undefined) {
            messages_overlay_ui.try_set_initial_element(
                focused_draft_id,
                keyboard_handling_context,
            );
        }
        for (const [selector, scroll_top] of scroll_tops) {
            const $list = $(selector);
            if ($list.length > 0 && scroll_top > 0) {
                scroll_util.get_scroll_element($list).scrollTop(scroll_top);
            }
        }
    }, 0);
}

function rerender_drafts(): void {
    const overlay_state = capture_overlay_state();

    const {narrow_drafts, other_drafts, narrow_drafts_header, outbox_drafts} =
        get_formatted_drafts_data();
    if (outbox_drafts.length === 0) {
        current_tab = "drafts";
    } else if (
        narrow_drafts.length + other_drafts.length === 0 &&
        outbox_drafts.length > rendered_outbox_count
    ) {
        // Gate on growth: deleting the last draft must not move the user here.
        current_tab = "outbox";
    }
    render_widgets(narrow_drafts, other_drafts, narrow_drafts_header, outbox_drafts);
    setup_event_handlers();
    restore_overlay_state(overlay_state);
}

export function launch(): void {
    const {narrow_drafts, other_drafts, narrow_drafts_header, outbox_drafts} =
        get_formatted_drafts_data();
    const drafts_empty = narrow_drafts.length === 0 && other_drafts.length === 0;
    current_tab = drafts_empty && outbox_drafts.length > 0 ? "outbox" : "drafts";

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
        // Delay focus initialization until the overlay DOM is fully rendered.
        // Otherwise, get_focused_element_id() returns undefined and the focus
        // may not be applied.
        setTimeout(() => {
            focus_first_row_of_current_tab();
        }, 0);
    }
    setup_event_handlers();
    setup_bulk_actions_handlers();
    drafts.set_draft_rerender_listener(rerender_drafts);
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
            draft_undo_list = [];
            draft_undo_action = undefined;
            drafts.set_draft_rerender_listener(undefined);
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

    $("body").on("focus", "#draft_overlay", (e) => {
        if (!(e.target instanceof HTMLElement)) {
            return;
        }
        const draft_row = e.target.closest(".overlay-message-info-box");
        if (draft_row instanceof HTMLElement) {
            // A draft gained focus; mark it as the selected draft.
            messages_overlay_ui.activate_element(draft_row, keyboard_handling_context);
        } else if (e.target.matches(overlay_util.OVERLAY_FOCUSABLE_SELECTOR)) {
            // Another focusable element (e.g. a header button) gained focus;
            // draft info-boxes are already handled by the branch above, so
            // the `.overlay-message-info-box` part of the selector never
            // matches here.
            // Only clear the draft selection when the control was reached via
            // keyboard (Tab), where both it and the draft would show a focus
            // ring; a pointer click shows no ring on the control, so keep the
            // selection.
            if (e.target.matches(":focus-visible")) {
                $("#drafts_table .overlay-message-info-box").removeClass("active");
            }
        } else {
            // Focus landed on a non-interactive area. Return focus to the
            // selected draft or the first one if none is selected, so that
            // keyboard navigation continues from a draft.
            const draft_to_focus =
                $("#drafts_table .overlay-message-info-box.active")[0] ??
                $("#drafts_table .overlay-message-info-box")[0];
            if (draft_to_focus !== undefined) {
                messages_overlay_ui.activate_element(draft_to_focus, keyboard_handling_context);
            }
        }
    });
    // Delegated, so it runs after the toggler has switched panes.
    $("body").on("click", "#draft-overlay-tab-switcher .ind-tab", () => {
        focus_first_row_of_current_tab();
    });
    $("body").on(
        "click",
        "#draft_overlay_banner_container .draft-delete-banner-undo-button",
        undo_discarded_drafts,
    );
    $("body").on("click", "#draft_overlay_banner_container .banner-close-button", clear_undo_list);
}
