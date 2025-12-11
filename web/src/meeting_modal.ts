import $ from "jquery";

import * as channel from "./channel.ts";
import * as compose_state from "./compose_state.ts";
import {$t_html} from "./i18n.ts";
import * as ui_report from "./ui_report.ts";

interface MeetingCreateResponse {
    message_id: number;
    room_name: string;
    join_url: string;
    domain: string;
    jwt: string;
}

export function start_meeting(e: JQuery.ClickEvent): void {
    e.preventDefault();
    e.stopPropagation();

    const title =
        $<HTMLInputElement>("#meeting-title-input").val()?.trim() || "Video Meeting";

    const stream_id = compose_state.stream_id();
    const topic = compose_state.topic();
    const private_message_recipient_ids = compose_state.private_message_recipient_user_ids();

    const data: Record<string, string | number | undefined> = {
        title,
    };

    if (stream_id !== undefined) {
        data.stream_id = stream_id;
        data.topic = topic;
    } else if (private_message_recipient_ids.length > 0) {
        data.private_message_recipient_ids = JSON.stringify(private_message_recipient_ids);
    }

    channel.post({
        url: "/json/meetings/create",
        data,
        success(response) {
            const meeting_data = response as MeetingCreateResponse;
            // Open the meeting in a new tab for the creator
            window.open(meeting_data.join_url, "_blank");
        },
        error(xhr) {
            ui_report.error(
                $t_html({defaultMessage: "Failed to create meeting."}),
                xhr,
                $("#dialog_error"),
            );
        },
    });
}
