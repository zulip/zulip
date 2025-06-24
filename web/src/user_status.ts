import {z} from "zod";

import * as channel from "./channel.ts";
import * as emoji from "./emoji.ts";
import type {EmojiRenderingDetails} from "./emoji.ts";
import type {StateData} from "./state_data.ts";
import {user_settings} from "./user_settings.ts";
import {user_status_schema} from "./user_status_types.ts";

export type UserStatus = z.infer<typeof user_status_schema>;
export type UserStatusEmojiInfo = EmojiRenderingDetails & {
    emoji_alt_code?: boolean;
};

const user_status_event_schema = z.intersection(
    z.object({
        id: z.number(),
        type: z.literal("user_status"),
        user_id: z.number(),
    }),
    user_status_schema,
);

export type TimeKey =
    | "never"
    | "in_thirty_minutes"
    | "in_one_hour"
    | "today_five_pm"
    | "tomorrow"
    | "custom";

export type UserStatusEvent = z.infer<typeof user_status_event_schema>;

const user_info = new Map<number, string>();
const user_status_emoji_info = new Map<number, UserStatusEmojiInfo>();

let scheduled_end_time: number | undefined;

export function set_scheduled_end_time(scheduled_time: number | undefined): void {
    scheduled_end_time = scheduled_time;
}

export function get_scheduled_end_time(): number | undefined {
    return scheduled_end_time;
}

export function server_update_status(opts: {
    status_text: string;
    emoji_name: string;
    emoji_code: string;
    reaction_type?: string;
    scheduled_end_time: number | undefined;
    success?: () => void;
}): void {
    void channel.post({
        url: "/json/users/me/status",
        data: {
            status_text: opts.status_text,
            emoji_name: opts.emoji_name,
            emoji_code: opts.emoji_code,
            reaction_type: opts.reaction_type,
            scheduled_end_time: opts.scheduled_end_time,
        },
        success() {
            if (opts.success) {
                opts.success();
            }
        },
    });
}

export function server_invisible_mode_on(): void {
    void channel.patch({
        url: "/json/settings",
        data: {
            presence_enabled: false,
        },
    });
}

export function server_invisible_mode_off(): void {
    void channel.patch({
        url: "/json/settings",
        data: {
            presence_enabled: true,
        },
    });
}

export function get_status_text(user_id: number): string | undefined {
    return user_info.get(user_id);
}

export function set_status_text(opts: {user_id: number; status_text: string}): void {
    if (!opts.status_text) {
        user_info.delete(opts.user_id);
        return;
    }

    user_info.set(opts.user_id, opts.status_text);
}

export function get_status_emoji(user_id: number): UserStatusEmojiInfo | undefined {
    return user_status_emoji_info.get(user_id);
}

export function set_status_emoji(event: UserStatusEvent): void {
    // TODO/typescript: Move validation to the caller when
    // server_events_dispatch.js is converted to TypeScript.
    const opts = user_status_event_schema.parse(event);

    if (!opts.emoji_name) {
        user_status_emoji_info.delete(opts.user_id);
        return;
    }

    user_status_emoji_info.set(opts.user_id, {
        emoji_alt_code: user_settings.emojiset === "text",
        ...emoji.get_emoji_details_for_rendering({
            emoji_name: opts.emoji_name,
            emoji_code: opts.emoji_code,
            reaction_type: opts.reaction_type,
        }),
    });
}

export function compute_scheduled_end_time(
    custom_time_selected?: number,
): Record<TimeKey, number | undefined> {
    const end_times: Record<string, number | undefined> = {};

    const now = new Date();
    now.setSeconds(0, 0);
    const today = new Date(now);
    const tomorrow = new Date(new Date(now).setDate(now.getDate() + 1));
    // Since setHours returns a timestamp, it's safe to mutate the
    // original date objects here.
    end_times.never = undefined;
    // 30 minutes from now
    end_times.in_thirty_minutes = new Date(now).setMinutes(now.getMinutes() + 30);
    // 1 hour from now
    end_times.in_one_hour = new Date(now).setHours(now.getHours() + 1);
    // today at 5pm
    end_times.today_five_pm = today.setHours(17, 0, 0, 0);
    // tomorrow at 12am
    end_times.tomorrow = tomorrow.setHours(0, 0, 0, 0);
    end_times.custom = custom_time_selected;

    return end_times;
}

export function initialize(params: StateData["user_status"]): void {
    user_info.clear();

    for (const [str_user_id, dct] of Object.entries(params.user_status)) {
        // JSON does not allow integer keys, so we
        // convert them here.
        const user_id = Number.parseInt(str_user_id, 10);

        if (dct.status_text) {
            user_info.set(user_id, dct.status_text);
        }

        set_scheduled_end_time(dct.scheduled_end_time);

        if (dct.emoji_name) {
            user_status_emoji_info.set(user_id, {
                ...emoji.get_emoji_details_for_rendering(dct),
            });
        }
    }
}
