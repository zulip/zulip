export function get_hash_category(hash?: string): string {
    // given "#streams/subscribed", returns "streams"
    return hash ? hash.replace(/^#/, "").split(/\//)[0] : "";
}

export function get_hash_section(hash?: string): string {
    // given "#settings/profile", returns "profile"
    // given '#streams/5/social", returns "5"
    if (!hash) {
        return "";
    }

    const parts = hash.replace(/\/$/, "").split(/\//);

    return parts[1] || "";
}

export function get_current_nth_hash_section(n: number): string {
    const hash = window.location.hash;
    // given "#settings/profile" and n=2, returns "profile"
    // given '#streams/5/social" and n=3, returns "social"
    const parts = hash.replace(/\/$/, "").split(/\//);
    if (parts.length < n) {
        return "";
    }

    return parts[n - 1] || "";
}

export function get_current_hash_category(): string {
    return get_hash_category(window.location.hash);
}

export function get_current_hash_section(): string {
    return get_hash_section(window.location.hash);
}

export function is_overlay_hash(hash: string): boolean {
    // Hash changes within this list are overlays and should not unnarrow (etc.)
    const overlay_list = [
        "streams",
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

    if (hash_components[0] !== "streams") {
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
    return window.location.hash === "#streams/new";
}

export const allowed_web_public_narrows = [
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
        "all_messages",
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
