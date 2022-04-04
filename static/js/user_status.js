import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as emoji from "./emoji";
import {user_settings} from "./user_settings";

const away_user_ids = new Set();
const user_info = new Map();
const user_status_emoji_info = new Map();

export function server_update(opts) {
    channel.post({
        url: "/json/users/me/status",
        data: {
            away: opts.away,
            status_text: opts.status_text,
            emoji_name: opts.emoji_name,
            emoji_code: opts.emoji_code,
            reaction_type: opts.reaction_type,
        },
        idempotent: true,
        success() {
            if (opts.success) {
                opts.success();
            }
        },
    });
}

export function server_set_away() {
    server_update({away: true});
}

export function server_revoke_away() {
    server_update({away: false});
}

export function set_away(user_id) {
    if (typeof user_id !== "number") {
        blueslip.error("need ints for user_id");
    }
    away_user_ids.add(user_id);
}

export function revoke_away(user_id) {
    if (typeof user_id !== "number") {
        blueslip.error("need ints for user_id");
    }
    away_user_ids.delete(user_id);
}

export function is_away(user_id) {
    return away_user_ids.has(user_id);
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
    away_user_ids.clear();
    user_info.clear();

    for (const [str_user_id, dct] of Object.entries(params.user_status)) {
        // JSON does not allow integer keys, so we
        // convert them here.
        const user_id = Number.parseInt(str_user_id, 10);

        if (dct.away) {
            away_user_ids.add(user_id);
        }

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
