import * as emoji from "../shared/js/emoji";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import {page_params} from "./page_params";

const away_user_ids = new Set();
const user_info = new Map();

export function server_update(opts) {
    channel.post({
        url: "/json/users/me/status",
        data: {
            away: opts.away,
            status_text: opts.status_text,
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

// This function will add missing/extra parameters to the emoji info object,
// that would need by template to render an emoji.
export function get_emoji_info(emoji_info) {
    // To call this function you must pass at least an emoji name.
    if (!emoji_info || !emoji_info.emoji_name) {
        return {};
    }

    const status_emoji_info = {...emoji_info};

    status_emoji_info.emoji_alt_code = page_params.emojiset === "text";
    if (status_emoji_info.emoji_alt_code) {
        return status_emoji_info;
    }

    if (emoji.active_realm_emojis.has(emoji_info.emoji_name)) {
        if (!emoji_info.reaction_type) {
            if (emoji_info.emoji_name === "zulip") {
                status_emoji_info.reaction_type = "zulip_extra_emoji";
            } else {
                status_emoji_info.reaction_type = "realm_emoji";
            }
        }
        const more_emoji_info = emoji.active_realm_emojis.get(emoji_info.emoji_name);
        status_emoji_info.emoji_code = emoji_info.emoji_code || more_emoji_info.id;
        status_emoji_info.url = more_emoji_info.emoji_url;
    } else {
        const codepoint = emoji.get_emoji_codepoint(emoji_info.emoji_name);
        if (codepoint === undefined) {
            blueslip.warn("Bad emoji name: " + emoji_info.emoji_name);
            return {};
        }
        status_emoji_info.reaction_type = emoji_info.reaction_type || "unicode_emoji";
        status_emoji_info.emoji_code = emoji_info.emoji_code || codepoint;
    }
    return status_emoji_info;
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
    }
}
