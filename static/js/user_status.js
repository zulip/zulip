import * as channel from "./channel";
import * as emoji from "./emoji";
import {user_settings} from "./user_settings";

const user_info = new Map();
const user_status_emoji_info = new Map();

export function server_update_status(opts) {
    channel.post({
        url: "/json/users/me/status",
        data: {
            status_text: opts.status_text,
            emoji_name: opts.emoji_name,
            emoji_code: opts.emoji_code,
            reaction_type: opts.reaction_type,
        },
        success() {
            if (opts.success) {
                opts.success();
            }
        },
    });
}

export function server_invisible_mode_on() {
    channel.patch({
        url: "/json/settings",
        data: {
            presence_enabled: false,
        },
    });
}

export function server_invisible_mode_off() {
    channel.patch({
        url: "/json/settings",
        data: {
            presence_enabled: true,
        },
    });
}

export function get_status_text(user_id) {
    return user_info.get(user_id);
}

export function set_status_text(opts) {
    if (!opts.status_text) {
        user_info.delete(opts.user_id);
        return;
    }

    user_info.set(opts.user_id, opts.status_text);
}

export function get_status_emoji(user_id) {
    return user_status_emoji_info.get(user_id);
}

export function set_status_emoji(opts) {
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

export function initialize(params) {
    user_info.clear();

    for (const [str_user_id, dct] of Object.entries(params.user_status)) {
        // JSON does not allow integer keys, so we
        // convert them here.
        const user_id = Number.parseInt(str_user_id, 10);

        if (dct.status_text) {
            user_info.set(user_id, dct.status_text);
        }

        if (dct.emoji_name) {
            user_status_emoji_info.set(user_id, {
                ...emoji.get_emoji_details_for_rendering(dct),
            });
        }
    }
}
