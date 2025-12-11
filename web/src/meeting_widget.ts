import $ from "jquery";
import * as z from "zod/mini";

import render_message_hidden_dialog from "../templates/message_hidden_dialog.hbs";
import render_widgets_meeting_widget from "../templates/widgets/meeting_widget.hbs";

import * as blueslip from "./blueslip.ts";
import type {InboundData} from "./meeting_data.ts";
import {MeetingData} from "./meeting_data.ts";
import * as message_lists from "./message_lists.ts";
import type {Message} from "./message_store.ts";
import * as people from "./people.ts";
import type {WidgetExtraData} from "./widgetize.ts";

export type Event = {sender_id: number; data: InboundData};

export const meeting_widget_extra_data_schema = z.object({
    room_name: z.string(),
    title: z.optional(z.string()),
    host_id: z.number(),
    host_name: z.string(),
    domain: z.string(),
    status: z.enum(["active", "ended"]),
    created_at: z.string(),
    join_url: z.optional(z.string()),
});

export type MeetingWidgetExtraData = z.infer<typeof meeting_widget_extra_data_schema>;

export type MeetingWidgetOutboundData =
    | {type: "join"; user_id: number; user_name: string}
    | {type: "leave"; user_id: number}
    | {type: "end_meeting"; duration_seconds: number}
    | {type: "update_status"; status: "active" | "ended"};

export function activate({
    $elem,
    callback,
    extra_data,
    message,
}: {
    $elem: JQuery;
    callback: (data: MeetingWidgetOutboundData) => void;
    extra_data: WidgetExtraData;
    message: Message;
}): (events: Event[]) => void {
    const is_my_meeting = people.is_my_user_id(message.sender_id);
    const parse_result = meeting_widget_extra_data_schema.safeParse(extra_data);

    if (!parse_result.success) {
        blueslip.error("invalid meeting widget extra data", {issues: parse_result.error.issues});
        return (_events: Event[]): void => {
            /* noop */
        };
    }

    const parsed_extra_data = parse_result.data;

    // Build join URL if not provided
    const jaas_app_id = ""; // This would need to come from settings
    const join_url =
        parsed_extra_data.join_url ||
        `https://${parsed_extra_data.domain}/${jaas_app_id}/${parsed_extra_data.room_name}`;

    const meeting_data = new MeetingData({
        message_sender_id: message.sender_id,
        current_user_id: people.my_current_user_id(),
        room_name: parsed_extra_data.room_name,
        title: parsed_extra_data.title ?? "Video Meeting",
        host_id: parsed_extra_data.host_id,
        host_name: parsed_extra_data.host_name,
        domain: parsed_extra_data.domain,
        status: parsed_extra_data.status,
        created_at: parsed_extra_data.created_at,
        join_url,
        report_error_function: blueslip.warn,
    });

    const message_container = message_lists.current?.view.message_containers.get(message.id);

    let duration_timer: ReturnType<typeof setInterval> | null = null;

    function render_widget(): void {
        const widget_data = meeting_data.get_widget_data();
        const html = render_widgets_meeting_widget(widget_data);
        $elem.html(html);

        // Set up join button click handler
        $elem.find(".meeting-join-button").on("click", (e) => {
            e.stopPropagation();
            // The link opens in a new tab via href, but we could also track the join
            const data = meeting_data.handle.join.outbound(
                people.my_current_user_id(),
                people.my_full_name(),
            );
            callback(data);
        });

        // Set up copy link button
        $elem.find(".meeting-copy-link").on("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            void navigator.clipboard.writeText(meeting_data.join_url);
            // Could show a toast notification here
        });

        // Set up end meeting button (only visible to host)
        $elem.find(".meeting-end-button").on("click", (e) => {
            e.preventDefault();
            e.stopPropagation();

            const start = new Date(meeting_data.created_at);
            const now = new Date();
            const duration_seconds = Math.floor((now.getTime() - start.getTime()) / 1000);

            const data = meeting_data.handle.end_meeting.outbound(duration_seconds);
            if (data) {
                callback(data);
            }
        });

        // Start/stop duration timer
        if (meeting_data.is_active() && !duration_timer) {
            duration_timer = setInterval(() => {
                const $duration = $elem.find(".meeting-duration-time");
                if ($duration.length > 0) {
                    const start = new Date(meeting_data.created_at);
                    const now = new Date();
                    const seconds = Math.floor((now.getTime() - start.getTime()) / 1000);
                    $duration.text(meeting_data.format_duration(seconds));
                }
            }, 1000);
        } else if (!meeting_data.is_active() && duration_timer) {
            clearInterval(duration_timer);
            duration_timer = null;
        }
    }

    const handle_events = function (events: Event[]): void {
        // Don't process events for hidden messages
        if (message_container?.is_hidden) {
            return;
        }

        for (const event of events) {
            meeting_data.handle_event(event.sender_id, event.data);
        }

        render_widget();
    };

    if (message_container?.is_hidden) {
        const html = render_message_hidden_dialog();
        $elem.html(html);
    } else {
        render_widget();
    }

    return handle_events;
}
