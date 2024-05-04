export function get_hash_category(hash?: string): string {
    // given "#channels/subscribed", returns "channels"
    return hash ? hash.replace(/^#/, "").split(/\//)[0] : "";
}

export function get_hash_section(hash?: string): string {
    // given "#settings/profile", returns "profile"
    // given '#channels/5/social", returns "5"
    if (!hash) {
        return "";
    }

    const parts = hash.replace(/\/$/, "").split(/\//);

    return parts[1] || "";
}

function get_nth_hash_section(hash: string, n: number): string {
    // given "#settings/profile" and n=1, returns "profile"
    // given '#channels/5/social" and n=2, returns "social"
    const parts = hash.replace(/\/$/, "").split(/\//);
    return parts.at(n) ?? "";
}

export function get_current_nth_hash_section(n: number): string {
    return get_nth_hash_section(window.location.hash, n);
}

export function get_current_hash_category(): string {
    return get_hash_category(window.location.hash);
}

export function get_current_hash_section(): string {
    return get_hash_section(window.location.hash);
}

export function is_same_server_message_link(url: string): boolean {
    // A same server message link always has category `narrow`,
    // section `stream` or `dm`, and ends with `/near/<message_id>`,
    // where <message_id> is a sequence of digits.
    return (
        get_hash_category(url) === "narrow" &&
        (get_hash_section(url) === "stream" || get_hash_section(url) === "dm") &&
        get_nth_hash_section(url, -2) === "near" &&
        /^\d+$/.test(get_nth_hash_section(url, -1))
    );
}

export function is_overlay_hash(hash: string): boolean {
    // Hash changes within this list are overlays and should not unnarrow (etc.)
    const overlay_list = [
        // In 2024, stream was renamed to channel in the Zulip API and UI.
        // Because pre-change Welcome Bot and Notification Bot messages
        // included links to "/#streams/all" and "/#streams/new", we'll
        // need to support "streams" as an overlay hash as an alias for
        // "channels" permanently.
        "streams",
        "channels",
        "drafts",
        "groups",
        "settings",
        "organization",
        "invite",
        "keyboard-shortcuts",
        "message-formatting",
        "search-operators",
        "about-zulip",
        "scheduled",
        "user",
    ];
    const main_hash = get_hash_category(hash);

    return overlay_list.includes(main_hash);
}

// this finds the stream that is actively open in the settings and focused in
// the left side.
export function is_editing_stream(desired_stream_id: number): boolean {
    const hash_components = window.location.hash.slice(1).split(/\//);

    if (hash_components[0] !== "channels") {
        return false;
    }

    if (!hash_components[2]) {
        return false;
    }

    // if the string casted to a number is valid, and another component
    // after exists then it's a stream name/id pair.
    const stream_id = Number.parseFloat(hash_components[1]);

    return stream_id === desired_stream_id;
}

export function is_create_new_stream_narrow(): boolean {
    return window.location.hash === "#channels/new";
}

// This checks whether the user is in the stream settings menu
// and is opening the 'Subscribers' tab on the right panel.
export function is_subscribers_section_opened_for_stream(): boolean {
    const hash_components = window.location.hash.slice(1).split(/\//);

    if (hash_components[0] !== "channels") {
        return false;
    }
    if (!hash_components[3]) {
        return false;
    }
    return hash_components[3] === "subscribers";
}

export const allowed_web_public_narrows = [
    "channels",
    "channel",
    "streams",
    "stream",
    "topic",
    "sender",
    "has",
    "search",
    "near",
    "id",
];

export function is_spectator_compatible(hash: string): boolean {
    // Defines which views are supported for spectators.
    // This implementation should agree with the similar function in zerver/lib/narrow.py.
    const web_public_allowed_hashes = [
        "",
        // full #narrow hash handled in filter.is_spectator_compatible
        "narrow",
        // TODO/compatibility: #recent_topics was renamed to #recent
        // in 2022. We should support the old URL fragment at least
        // until one cannot directly upgrade from Zulip 5.x.
        "recent_topics",
        "recent",
        "keyboard-shortcuts",
        "message-formatting",
        "search-operators",
        // TODO/compatibility: #all_messages was renamed to #feed
        // in 2024. We should support the old URL fragment at least
        // until one cannot directly upgrade from Zulip 8.x.
        "all_messages",
        "feed",
        "about-zulip",
    ];

    const main_hash = get_hash_category(hash);

    if (main_hash === "narrow") {
        const hash_section = get_hash_section(hash);
        if (!allowed_web_public_narrows.includes(hash_section)) {
            return false;
        }
        return true;
    }

    return web_public_allowed_hashes.includes(main_hash);
}
