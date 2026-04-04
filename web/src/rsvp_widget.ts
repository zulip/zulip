import $ from "jquery";
import assert from "minimalistic-assert";

import * as people from "./people.ts";
import { RsvpData, vote_schema, type RsvpResponse } from "./rsvp_data.ts";
import { ZulipWidgetContext } from "./widget_context.ts";
import type { AnyWidgetData, WidgetData } from "./widget_schema.ts";
import type { Event } from "./widget_data.ts";
import * as timerender from "./timerender.ts";

export function activate({
    any_data,
    message,
}: {
    any_data: AnyWidgetData;
    message: any;
}): { inbound_events_handler: (events: Event[]) => void; widget_data: WidgetData } {
    assert(any_data.widget_type === "rsvp");
    const { extra_data } = any_data;
    const widget_context = new ZulipWidgetContext(message);

    const rsvp_data = new RsvpData({
        topic: extra_data.topic,
        datetime: extra_data.datetime,
        invitees: extra_data.invitees ?? [],
        current_user_id: people.my_current_user_id(),
    });

    const widget_data = { widget_type: "rsvp" as const, data: rsvp_data };

    function handle_events(events: Event[]): void {
        for (const event of events) {
            const parsed = vote_schema.safeParse(event.data);
            if (parsed.success) {
                rsvp_data.handle_vote_event(event.sender_id, parsed.data);
            }
        }
    }

    return { inbound_events_handler: handle_events, widget_data };
}

function format_datetime(iso: string): string {
    const dt = new Date(iso);
    if (Number.isNaN(dt.getTime())) {
        return iso;
    }
    const day_of_week = dt.toLocaleDateString("en-US", { weekday: "long" });
    const month = dt.toLocaleDateString("en-US", { month: "long" });
    const day = dt.getDate();
    const time = dt.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
    return `${day_of_week}, ${month} ${day} @<span class="rsvp-time">${time}</span>`;
}

export function render({
    $elem,
    callback,
    widget_data,
}: {
    $elem: JQuery;
    callback: (data: any) => void;
    widget_data: WidgetData;
    message: any;
    rerender: boolean;
}): void {
    assert(widget_data.widget_type === "rsvp");
    const rsvp_data = widget_data.data as RsvpData;
    const { topic, datetime, buckets, my_response } = rsvp_data.get_widget_data();

    function names(ids: number[]): string {
        return ids.map((id) => people.get_by_user_id(id)?.full_name ?? "").filter(Boolean).join(", ");
    }

    const buttons: {status: RsvpResponse; icon: string; label: string}[] = [
        {status: "accept",    icon: "message-circle-check",           label: "Accept"},
        {status: "tentative", icon: "message-circle-question-mark",   label: "Tentative"},
        {status: "decline",   icon: "message-circle-x",               label: "Decline"},
    ];

    const buttons_html = buttons
        .map(({status, icon, label}) => {
            const is_active = my_response === status ? "rsvp-active" : "";
            const count = buckets[status].length;
            const responders = names(buckets[status]);
            return `
            <div class="rsvp-option ${is_active}" data-status="${status}">
                <button class="rsvp-vote-btn" data-status="${status}">
                    <i class="zulip-icon zulip-icon-${icon}" aria-hidden="true"></i>
                    <span class="rsvp-label">${label}</span>
                    ${count > 0 ? `<span class="rsvp-count">${count}</span>` : ""}
                </button>
                ${responders ? `<div class="rsvp-names">${responders}</div>` : ""}
            </div>`;
        })
        .join("");

    const html = `
        <div class="rsvp-widget">
            <div class="rsvp-topic">${topic}</div>
            <div class="rsvp-datetime">${format_datetime(datetime)}</div>
            <div class="rsvp-actions">${buttons_html}</div>
        </div>`;
 
    $elem.html(html);
 
    $elem.find(".rsvp-vote-btn").on("click", function () {
        const status = $(this).attr("data-status") as RsvpResponse;
        const event = rsvp_data.vote_event(status);
        rsvp_data.handle_vote_event(rsvp_data.me, event);
        callback(event);
        render({$elem, callback, widget_data, message: null, rerender: true});
    });
}