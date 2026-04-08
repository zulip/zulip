import $ from "jquery";
import _ from "lodash";

import render_create_recurring_scheduled_message_modal from "../templates/create_recurring_scheduled_message_modal.hbs";
import render_recurring_scheduled_messages_overlay from "../templates/recurring_scheduled_messages_overlay.hbs";

import * as browser_history from "./browser_history.ts";
import * as channel from "./channel.ts";
import * as compose_state from "./compose_state.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import * as overlays from "./overlays.ts";
import * as people from "./people.ts";
import * as recurring_scheduled_messages from "./recurring_scheduled_messages.ts";
import type {RecurringScheduledMessage} from "./recurring_scheduled_messages.ts";
import * as stream_data from "./stream_data.ts";
import * as sub_store from "./sub_store.ts";
import * as timerender from "./timerender.ts";
import * as ui_report from "./ui_report.ts";

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

type MonthlyRecurrenceDays =
    | {
          type: "calendar_day";
          day?: number;
      }
    | {
          type: "ordinal_weekday";
          ordinal?: number;
          weekday?: number;
      };

// In-modal destination list, rebuilt each time the modal opens.
type StreamDestination = {type: "stream"; stream_id: number; topic: string};
type DirectDestination = {type: "direct"; user_ids: number[]};
type Destination = StreamDestination | DirectDestination;
let pending_destinations: Destination[] = [];

// ---------------------------------------------------------------------------
// Formatting helpers (used by the overlay list)
// ---------------------------------------------------------------------------

function format_recurrence(rsm: RecurringScheduledMessage): string {
    if (rsm.recurrence_type === "one_time") {
        const date = new Date(rsm.next_delivery * 1000);
        return timerender.get_full_datetime(date, "time");
    }
    if (rsm.recurrence_type === "daily") {
        return `Daily at ${rsm.scheduled_time} UTC`;
    }
    if (rsm.recurrence_type === "monthly" && !Array.isArray(rsm.recurrence_days)) {
        const rule = rsm.recurrence_days as MonthlyRecurrenceDays;
        if (rule.type === "calendar_day") {
            const day_label = rule.day === -1 ? "last day" : `${rule.day}`;
            return `Monthly (${day_label}) at ${rsm.scheduled_time} UTC`;
        }

        const ordinal_labels = new Map([
            [1, "first"],
            [2, "second"],
            [3, "third"],
            [4, "fourth"],
            [-1, "last"],
        ]);
        const ordinal = ordinal_labels.get(rule.ordinal ?? 1) ?? String(rule.ordinal);
        const weekday = DAY_NAMES[rule.weekday ?? 0] ?? String(rule.weekday);
        return `Monthly (${ordinal} ${weekday}) at ${rsm.scheduled_time} UTC`;
    }

    const recurrence_days = Array.isArray(rsm.recurrence_days) ? rsm.recurrence_days : [];
    const day_labels = recurrence_days.map((d) => DAY_NAMES[d]).join(", ");
    const label = rsm.recurrence_type === "weekly" ? "Weekly" : "Specific days";
    return `${label} (${day_labels}) at ${rsm.scheduled_time} UTC`;
}

function get_dialog_error_element(): JQuery {
    return $("#dialog_error").expectOne();
}

function show_modal_error(message: string): void {
    ui_report.client_error(message, get_dialog_error_element());
}

function clear_modal_error(): void {
    get_dialog_error_element().hide().empty();
}

function format_destination(dest: Record<string, unknown>): string {
    if (dest["type"] === "stream") {
        const stream_id = dest["stream_id"] as number;
        const stream = sub_store.get(stream_id);
        const name = stream ? stream.name : `#${stream_id}`;
        return `${name} > ${dest["topic"] as string}`;
    }
    const user_ids = dest["user_ids"] as number[];
    const names = user_ids.map((uid) => {
        const person = people.maybe_get_user_by_id(uid);
        return person ? person.full_name : String(uid);
    });
    return `DM: ${names.join(", ")}`;
}

// ---------------------------------------------------------------------------
// Overlay rendering
// ---------------------------------------------------------------------------

function render_list(): void {
    const all = recurring_scheduled_messages.get_all();
    const $list = $("#recurring_scheduled_messages_overlay .recurring-scheduled-messages-list");
    $list.find(".recurring-scheduled-message-row").remove();

    if (all.length === 0) {
        $list.find(".no-overlay-messages").show();
        return;
    }
    $list.find(".no-overlay-messages").hide();

    for (const rsm of all) {
        const dest_text = rsm.destinations
            .map((d) => format_destination(d as Record<string, unknown>))
            .join("; ");
        const $row = $(`
            <div class="recurring-scheduled-message-row" data-rsm-id="${rsm.id}">
                <div class="rsm-content">${_.escape(rsm.content)}</div>
                <div class="rsm-recurrence">${_.escape(format_recurrence(rsm))}</div>
                <div class="rsm-destinations">${_.escape(dest_text)}</div>
                <button class="rsm-cancel-btn button small rounded" data-rsm-id="${rsm.id}">
                    ${$t({defaultMessage: "Cancel"})}
                </button>
            </div>
        `);
        $list.append($row);
    }
}

export function rerender(): void {
    if (!overlays.recurring_scheduled_messages_open()) {
        return;
    }
    render_list();
}

export function launch(): void {
    $("#recurring-scheduled-messages-overlay-container").html(
        render_recurring_scheduled_messages_overlay(),
    );
    overlays.open_overlay({
        name: "recurring-scheduled",
        $overlay: $("#recurring_scheduled_messages_overlay"),
        on_close() {
            browser_history.exit_overlay();
        },
    });
    render_list();
}

// ---------------------------------------------------------------------------
// In-modal destination list rendering
// ---------------------------------------------------------------------------

function render_pending_destinations(): void {
    const $list = $("#rsm-destinations-list");
    $list.empty();

    for (const [idx, dest] of pending_destinations.entries()) {
        let label: string;
        if (dest.type === "stream") {
            const stream = sub_store.get(dest.stream_id);
            const name = stream ? stream.name : String(dest.stream_id);
            label = `${_.escape(name)} > ${_.escape(dest.topic)}`;
        } else {
            const names = dest.user_ids.map((uid) => {
                const person = people.maybe_get_user_by_id(uid);
                return _.escape(person ? person.full_name : String(uid));
            });
            label = `DM: ${names.join(", ")}`;
        }
        const $chip = $(`
            <div class="rsm-destination-chip">
                <span>${label}</span>
                <button type="button" class="rsm-remove-dest-btn" data-idx="${idx}">&times;</button>
            </div>
        `);
        $list.append($chip);
    }
}

// ---------------------------------------------------------------------------
// Add-destination handlers
// ---------------------------------------------------------------------------

function add_stream_destination(): void {
    const stream_name = ($<HTMLInputElement>("#rsm-stream-name-input").val() ?? "").trim();
    const topic = ($<HTMLInputElement>("#rsm-topic-input").val() ?? "").trim();

    if (!stream_name || !topic) {
        return;
    }

    const stream_id = stream_data.get_stream_id(stream_name);
    if (stream_id === undefined) {
        show_modal_error($t({defaultMessage: "Channel not found: {name}"}, {name: stream_name}));
        return;
    }

    pending_destinations.push({type: "stream", stream_id, topic});
    clear_modal_error();
    render_pending_destinations();
    $<HTMLInputElement>("#rsm-stream-name-input").val("");
    $<HTMLInputElement>("#rsm-topic-input").val("");
}

function add_direct_destination(): void {
    const raw = ($<HTMLInputElement>("#rsm-dm-emails-input").val() ?? "").trim();
    if (!raw) {
        return;
    }

    const emails = raw.split(",").map((e) => e.trim()).filter(Boolean);
    const user_ids: number[] = [];
    for (const email of emails) {
        const person = people.get_by_email(email);
        if (person === undefined) {
            show_modal_error($t({defaultMessage: "User not found: {email}"}, {email}));
            return;
        }
        user_ids.push(person.user_id);
    }

    pending_destinations.push({type: "direct", user_ids});
    clear_modal_error();
    render_pending_destinations();
    $<HTMLInputElement>("#rsm-dm-emails-input").val("");
}

function remove_destination(idx: number): void {
    pending_destinations.splice(idx, 1);
    render_pending_destinations();
}

// ---------------------------------------------------------------------------
// Create form submission
// ---------------------------------------------------------------------------

function submit_create_form(): void {
    const content = ($<HTMLTextAreaElement>("#recurring-scheduled-message-content").val() ?? "")
        .trim();
    const recurrence_type = $<HTMLSelectElement>(
        "#recurring-scheduled-message-recurrence-type",
    ).val() as string;
    const scheduled_time = $<HTMLInputElement>("#recurring-scheduled-message-time").val() as string;

    const recurrence_days: number[] = [];
    $("#create-recurring-scheduled-message-modal .recurrence-day-checkbox:checked").each(
        function () {
            recurrence_days.push(Number.parseInt($(this).val() as string, 10));
        },
    );

    if (pending_destinations.length === 0) {
        show_modal_error($t({defaultMessage: "Please add at least one destination."}));
        return;
    }

    const data: Record<string, unknown> = {
        content,
        recurrence_type,
        scheduled_time,
        destinations: JSON.stringify(pending_destinations),
        recurrence_days: JSON.stringify(recurrence_days),
    };

    if (recurrence_type === "one_time") {
        const datetime_val = (
            $<HTMLInputElement>("#recurring-scheduled-message-datetime").val() ?? ""
        );
        if (!datetime_val) {
            show_modal_error($t({defaultMessage: "Please choose a send time."}));
            return;
        }
        data["scheduled_delivery_timestamp"] = JSON.stringify(
            Math.floor(new Date(datetime_val).getTime() / 1000),
        );
    }

    clear_modal_error();
    dialog_widget.submit_api_request(channel.post, "/json/recurring_scheduled_messages", data);
}

// ---------------------------------------------------------------------------
// Modal post-render setup
// ---------------------------------------------------------------------------

function post_render_create_modal(): void {
    const $recurrence_type = $("#recurring-scheduled-message-recurrence-type");
    const $days_section = $("#recurrence-days-section");
    const $one_time_section = $("#one-time-timestamp-section");

    function update_visibility(): void {
        const val = $recurrence_type.val() as string;
        $days_section.toggle(val === "weekly" || val === "specific_days");
        $one_time_section.toggle(val === "one_time");
    }

    $recurrence_type.on("change", update_visibility);
    update_visibility();

    // Pre-populate from compose box context.
    const msg_type = compose_state.get_message_type();
    if (msg_type === "stream") {
        const stream_id = compose_state.stream_id();
        const topic = compose_state.topic();
        if (stream_id !== undefined && topic) {
            pending_destinations = [{type: "stream", stream_id, topic}];
        }
    } else if (msg_type === "private") {
        const user_ids = compose_state.private_message_recipient_ids();
        if (user_ids.length > 0) {
            pending_destinations = [{type: "direct", user_ids}];
        }
    }
    render_pending_destinations();

    // Wire add-destination buttons.
    $("#rsm-add-stream-btn").on("click", add_stream_destination);
    $("#rsm-add-direct-btn").on("click", add_direct_destination);

    // Wire remove-destination (event delegation on the list).
    $("#rsm-destinations-list").on("click", ".rsm-remove-dest-btn", (e) => {
        const idx = Number.parseInt($(e.currentTarget).attr("data-idx") ?? "0", 10);
        remove_destination(idx);
    });
}

export function open_create_modal(): void {
    pending_destinations = [];
    dialog_widget.launch({
        modal_title_html: $t_html({defaultMessage: "Create recurring scheduled message"}),
        modal_content_html: render_create_recurring_scheduled_message_modal(),
        modal_submit_button_text: $t({defaultMessage: "Schedule"}),
        id: "create-recurring-scheduled-message-modal",
        form_id: "create-recurring-scheduled-message-form",
        on_click: submit_create_form,
        post_render: post_render_create_modal,
    });
}

// ---------------------------------------------------------------------------
// Cancel button handler (overlay)
// ---------------------------------------------------------------------------

function handle_cancel_click(e: JQuery.ClickEvent): void {
    e.stopPropagation();
    const rsm_id = Number.parseInt($(e.currentTarget).attr("data-rsm-id") ?? "0", 10);

    confirm_dialog.launch({
        modal_title_html: $t_html({defaultMessage: "Cancel recurring scheduled message?"}),
        modal_content_html: $t({
            defaultMessage: "Are you sure you want to cancel this recurring scheduled message?",
        }),
        is_compact: true,
        on_click() {
            void channel.del({
                url: `/json/recurring_scheduled_messages/${rsm_id}`,
                success() {
                    recurring_scheduled_messages.remove(rsm_id);
                    rerender();
                },
            });
        },
    });
}

export function initialize(): void {
    $("body").on("click", ".rsm-cancel-btn", handle_cancel_click);
    $("body").on("click", ".rsm-create-btn", (e) => {
        e.preventDefault();
        e.stopPropagation();
        open_create_modal();
    });
}
