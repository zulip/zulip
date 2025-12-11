import assert from "minimalistic-assert";
import * as z from "zod/mini";

export type MeetingDataConfig = {
    message_sender_id: number;
    current_user_id: number;
    room_name: string;
    title: string;
    host_id: number;
    host_name: string;
    domain: string;
    status: "active" | "ended";
    created_at: string;
    join_url: string;
    report_error_function: (msg: string, more_info?: Record<string, unknown>) => void;
};

export type Participant = {
    user_id: number;
    user_name: string;
    joined_at: Date;
};

export type MeetingWidgetData = {
    room_name: string;
    title: string;
    host_id: number;
    host_name: string;
    domain: string;
    status: "active" | "ended";
    created_at: string;
    join_url: string;
    participants: Participant[];
    duration_seconds: number;
    is_active: boolean;
    is_host: boolean;
    participant_count: number;
    duration_display: string;
};

export type InboundData = unknown;
export type JoinOutboundData = {type: "join"; user_id: number; user_name: string};
export type LeaveOutboundData = {type: "leave"; user_id: number};
export type EndMeetingOutboundData = {type: "end_meeting"; duration_seconds: number};
export type UpdateStatusOutboundData = {type: "update_status"; status: "active" | "ended"};

export type MeetingHandle = {
    join: {
        outbound: (user_id: number, user_name: string) => JoinOutboundData;
        inbound: (sender_id: number, data: InboundData) => void;
    };
    leave: {
        outbound: (user_id: number) => LeaveOutboundData;
        inbound: (sender_id: number, data: InboundData) => void;
    };
    end_meeting: {
        outbound: (duration_seconds: number) => EndMeetingOutboundData | undefined;
        inbound: (sender_id: number, data: InboundData) => void;
    };
    update_status: {
        outbound: (status: "active" | "ended") => UpdateStatusOutboundData | undefined;
        inbound: (sender_id: number, data: InboundData) => void;
    };
};

const inbound_join_schema = z.object({
    type: z.literal("join"),
    user_id: z.number(),
    user_name: z.string(),
});

const inbound_leave_schema = z.object({
    type: z.literal("leave"),
    user_id: z.number(),
});

const inbound_end_meeting_schema = z.object({
    type: z.literal("end_meeting"),
    duration_seconds: z.number(),
});

const inbound_update_status_schema = z.object({
    type: z.literal("update_status"),
    status: z.enum(["active", "ended"]),
});

export class MeetingData {
    message_sender_id: number;
    me: number;
    room_name: string;
    title: string;
    host_id: number;
    host_name: string;
    domain: string;
    status: "active" | "ended";
    created_at: string;
    join_url: string;
    participants: Map<number, Participant>;
    duration_seconds: number;
    report_error_function: (error_message: string) => void;
    handle: MeetingHandle;

    constructor({
        message_sender_id,
        current_user_id,
        room_name,
        title,
        host_id,
        host_name,
        domain,
        status,
        created_at,
        join_url,
        report_error_function,
    }: MeetingDataConfig) {
        this.message_sender_id = message_sender_id;
        this.me = current_user_id;
        this.room_name = room_name;
        this.title = title;
        this.host_id = host_id;
        this.host_name = host_name;
        this.domain = domain;
        this.status = status;
        this.created_at = created_at;
        this.join_url = join_url;
        this.participants = new Map();
        this.duration_seconds = 0;
        this.report_error_function = report_error_function;

        this.handle = {
            join: {
                outbound: (user_id, user_name) => ({
                    type: "join",
                    user_id,
                    user_name,
                }),

                inbound: (_sender_id, data) => {
                    const safe_data = inbound_join_schema.parse(data);
                    this.participants.set(safe_data.user_id, {
                        user_id: safe_data.user_id,
                        user_name: safe_data.user_name,
                        joined_at: new Date(),
                    });
                },
            },

            leave: {
                outbound: (user_id) => ({
                    type: "leave",
                    user_id,
                }),

                inbound: (_sender_id, data) => {
                    const safe_data = inbound_leave_schema.parse(data);
                    this.participants.delete(safe_data.user_id);
                },
            },

            end_meeting: {
                outbound: (duration_seconds) => {
                    // Only the host can end the meeting
                    if (this.me !== this.host_id) {
                        return undefined;
                    }
                    return {
                        type: "end_meeting",
                        duration_seconds,
                    };
                },

                inbound: (sender_id, data) => {
                    // Only the host can end the meeting
                    if (sender_id !== this.message_sender_id) {
                        this.report_error_function(
                            `user ${sender_id} is not allowed to end the meeting`,
                        );
                        return;
                    }
                    const safe_data = inbound_end_meeting_schema.parse(data);
                    this.status = "ended";
                    this.duration_seconds = safe_data.duration_seconds;
                    this.participants.clear();
                },
            },

            update_status: {
                outbound: (status) => {
                    // Only the host can update status
                    if (this.me !== this.host_id) {
                        return undefined;
                    }
                    return {
                        type: "update_status",
                        status,
                    };
                },

                inbound: (sender_id, data) => {
                    // Only the host can update status
                    if (sender_id !== this.message_sender_id) {
                        this.report_error_function(
                            `user ${sender_id} is not allowed to update meeting status`,
                        );
                        return;
                    }
                    const safe_data = inbound_update_status_schema.parse(data);
                    this.status = safe_data.status;
                },
            },
        };
    }

    is_host(): boolean {
        return this.me === this.host_id;
    }

    is_active(): boolean {
        return this.status === "active";
    }

    get_widget_data(): MeetingWidgetData {
        const participants_array = [...this.participants.values()];
        const is_active = this.status === "active";

        // Calculate duration for display
        let duration_display = "";
        if (is_active) {
            const start = new Date(this.created_at);
            const now = new Date();
            const seconds = Math.floor((now.getTime() - start.getTime()) / 1000);
            duration_display = this.format_duration(seconds);
        } else if (this.duration_seconds > 0) {
            duration_display = this.format_duration(this.duration_seconds);
        }

        return {
            room_name: this.room_name,
            title: this.title,
            host_id: this.host_id,
            host_name: this.host_name,
            domain: this.domain,
            status: this.status,
            created_at: this.created_at,
            join_url: this.join_url,
            participants: participants_array,
            duration_seconds: this.duration_seconds,
            is_active,
            is_host: this.is_host(),
            participant_count: participants_array.length,
            duration_display,
        };
    }

    format_duration(seconds: number): string {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;

        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
        }
        return `${minutes}:${secs.toString().padStart(2, "0")}`;
    }

    handle_event(sender_id: number, data: InboundData): void {
        assert(
            typeof data === "object" &&
                data !== null &&
                "type" in data &&
                typeof data.type === "string",
        );
        const type = data.type as "join" | "leave" | "end_meeting" | "update_status";
        if (type === "join" || type === "leave" || type === "end_meeting" || type === "update_status") {
            this.handle[type].inbound(sender_id, data);
        } else {
            this.report_error_function(`meeting widget: unknown inbound type: ${type}`);
        }
    }
}
