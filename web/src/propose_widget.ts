import $ from "jquery";
import assert from "minimalistic-assert";

import * as channel from "./channel.ts";
import * as people from "./people.ts";
import * as rendered_markdown from "./rendered_markdown.ts";
import { ProposeData, availability_schema } from "./propose_data.ts";
import type { AnyWidgetData, WidgetData } from "./widget_schema.ts";
import type { Event } from "./widget_data.ts";
import { MeetingAvailabilityData } from "./meeting_availability_data.ts";
import type { AvailabilityEvent } from "./meeting_availability_data.ts";
import * as availability_modal from "./availability_modal.ts";

export function activate({
    any_data,
}: {
    any_data: AnyWidgetData;
    message: any;
}): { inbound_events_handler: (events: Event[]) => void; widget_data: WidgetData } {
    assert(any_data.widget_type === "propose_meeting");
    const { extra_data } = any_data;

    const propose_data = new ProposeData({
        meeting_id: extra_data.meeting_id,
        topic: extra_data.topic,
        invitees: extra_data.invitees ?? [],
        current_user_id: people.my_current_user_id(),
    });

    const widget_data: WidgetData = {
        widget_type: "propose_meeting",
        data: propose_data,
    };

    function handle_events(events: Event[]): void {
        for (const event of events) {
            const parsed = availability_schema.safeParse(event.data);
            if (parsed.success) {
                propose_data.handle_availability_event(event.sender_id, parsed.data);
            }
        }
    }

    return { inbound_events_handler: handle_events, widget_data };
}

function ordinal(n: number): string {
    const s = ["th", "st", "nd", "rd"];
    const v = n % 100;
    return s[(v - 20) % 10] ?? s[v] ?? s[0]!;
}

function format_deadline(deadline: string): string {
    const dt = new Date(deadline);
    const weekday = dt.toLocaleDateString("en-US", { weekday: "long" });
    const month = dt.toLocaleDateString("en-US", { month: "long" });
    const day = dt.getDate();
    const time = dt.toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
        timeZoneName: "short",
    });
    return `${weekday}, ${month} ${day}${ordinal(day)} @${time}`;
}

export function render({
    $elem,
    callback,
    widget_data,
    message,
}: {
    $elem: JQuery;
    callback: (data: any) => void;
    widget_data: WidgetData;
    message: any;
    rerender: boolean;
}): void {
    assert(widget_data.widget_type === "propose_meeting");
    const propose_data = widget_data.data as ProposeData;
    const { meeting_id, topic, invitees, submitted, i_have_submitted } =
        propose_data.get_widget_data();

    const me = people.my_current_user_id();
    const responded_count = submitted.size;
    const total_count = invitees.length;
    const is_invited = invitees.includes(me);
    const owner_id = message.sender_id;
    const is_owner = owner_id === me;
    const btn_label = is_owner
        ? "Review responses and confirm"
        : i_have_submitted
          ? "Edit Meeting Availability"
          : "Submit Meeting Availability";
    const deadline_action = is_owner ? "Review" : i_have_submitted ? "Edit" : "Submit";

    const invitees_html =
        invitees.length > 0
            ? invitees
                .map((id) => {
                    const user = people.get_by_user_id(id);
                    if (!user) return "";
                    const has_submitted = submitted.has(id);
                    return `
                        <div class="propose-invitee-row">
                            <span class="user-mention${id === propose_data.me ? " user-mention-me" : ""}" data-user-id="${id}">@${user.full_name}</span>${has_submitted ? " <em>(Responded)</em>" : ""}
                        </div>`;
                })
                .join("")
            : `<span class="rsvp-invitee-empty">No users invited</span>`;

    const html = `
        <div class="rsvp-widget propose-meeting-widget">
            <div class="rsvp-topic">${topic}</div>
            <div class="rsvp-invitees">
                <div class="rsvp-invitees-label">Invited Users</div>
                <em class="propose-response-count">Responses (${responded_count}/${total_count})</em>
                <div class="propose-invitees-list">${invitees_html}</div>
            </div>
            <div class="propose-meeting-actions">
                <a class="propose-availability-btn rsvp-add-all-users-link${!is_invited ? " disabled" : ""}"
                   role="button"
                   style="color: hsl(240deg 52% 67%);"
                   ${!is_invited ? 'title="You were not invited to this meeting"' : ""}>
                    ${btn_label}
                </a>
                <div style="padding-left: 8px; font-style: italic; font-size: 0.85em; margin-top: 2px;">
                    <em>${deadline_action} by <span class="propose-deadline-text"></span></em>
                </div>
            </div>
        </div>`;

    $elem.html(html);

    rendered_markdown.update_elements($elem.find(".propose-invitees-list"));

    // fetch meeting data for deadline display and button click handler
    void channel.get({
        url: `/json/meetings/${meeting_id}`,
        success(data) {
            const meeting = data as {
                deadline: string;
                owner_id: number;
                status: string;
                slots: { slot_id: number; start_time: string; end_time: string | null }[];
            };

            // show deadline
            $elem.find(".propose-deadline-text").text(format_deadline(meeting.deadline));

            const is_owner = meeting.owner_id === people.my_current_user_id();
            if (!is_invited && !is_owner) {
                return;
            }

            $elem.find(".propose-availability-btn").on("click", () => {
                if (is_owner) {
                    availability_modal.open(meeting_id, () => {
                        render({
                            $elem,
                            callback,
                            widget_data,
                            message,
                            rerender: true,
                        });
                    });
                    return;
                }

                // build dates and time range from slots
                const dates = [
                    ...new Set(meeting.slots.map((s) => s.start_time.slice(0, 10))),
                ].sort();
                const times = meeting.slots.map((s) => s.start_time.slice(11, 16));
                const start_time = times.reduce((a, b) => (a < b ? a : b));
                const end_time = times.reduce((a, b) => (a > b ? a : b));

                const sorted_times = [...new Set(times)].sort();
                let slot_duration_mins = 60;
                if (sorted_times.length >= 2) {
                    const [h1, m1] = sorted_times[0]!.split(":").map(Number);
                    const [h2, m2] = sorted_times[1]!.split(":").map(Number);
                    slot_duration_mins = (h2! * 60 + m2!) - (h1! * 60 + m1!);
                }

                const availability_data = new MeetingAvailabilityData({
                    topic,
                    dates,
                    start_time,
                    end_time,
                    slot_duration_mins,
                    invitees,
                    current_user_id: people.my_current_user_id(),
                });

                void import("./meeting_availability_submission_ui.ts").then(
                    ({ open_availability_modal }) => {
                        open_availability_modal(availability_data, (event: AvailabilityEvent) => {
                            // map available slot keys back to slot_ids for the backend
                            const slot_responses: Record<string, boolean> = {};
                            for (const slot of meeting.slots) {
                                // slot.start_time from backend is like "2026-04-19T10:00:00+00:00"
                                // availability slot keys are like "2026-04-19T10:00"
                                const slot_key = slot.start_time.slice(0, 16);
                                slot_responses[String(slot.slot_id)] =
                                    event.available_slots.includes(slot_key);
                            }

                            void channel.patch({
                                url: `/json/meetings/${meeting_id}/responses`,
                                data: {
                                    slot_responses: JSON.stringify(slot_responses),
                                },
                                success() {
                                    const av_event = propose_data.availability_event();
                                    propose_data.handle_availability_event(
                                        propose_data.me,
                                        av_event,
                                    );
                                    callback(av_event);
                                    render({
                                        $elem,
                                        callback,
                                        widget_data,
                                        message,
                                        rerender: true,
                                    });
                                },
                            });
                        });
                    },
                );
            });
        },
    });
}