"use strict";

// Read https://zulip.readthedocs.io/en/latest/subsystems/hashchange-system.html
// or locally: docs/subsystems/hashchange-system.md
let changing_hash = false;

function get_full_url(hash) {
    const location = window.location;

    if (hash === "" || hash.charAt(0) !== "#") {
        hash = "#" + hash;
    }

    // IE returns pathname as undefined and missing the leading /
    let pathname = location.pathname;
    if (pathname === undefined) {
        pathname = "/";
    } else if (pathname === "" || pathname.charAt(0) !== "/") {
        pathname = "/" + pathname;
    }

    // Build a full URL to not have same origin problems
    const url = location.protocol + "//" + location.host + pathname + hash;
    return url;
}

function set_hash(hash) {
    if (history.pushState) {
        const url = get_full_url(hash);
        history.pushState(null, null, url);
    } else {
        blueslip.warn("browser does not support pushState");
        window.location.hash = hash;
    }
}

function maybe_hide_recent_topics() {
    if (recent_topics.is_visible()) {
        recent_topics.hide();
        return true;
    }
    return false;
}

exports.changehash = function (newhash) {
    if (changing_hash) {
        return;
    }
    maybe_hide_recent_topics();
    message_viewport.stop_auto_scrolling();
    set_hash(newhash);
};

exports.save_narrow = function (operators) {
    if (changing_hash) {
        return;
    }
    const new_hash = hash_util.operators_to_hash(operators);
    exports.changehash(new_hash);
};

function activate_home_tab() {
    const coming_from_recent_topics = maybe_hide_recent_topics();
    ui_util.change_tab_to("#message_feed_container");
    narrow.deactivate(coming_from_recent_topics);
    floating_recipient_bar.update();
    search.update_button_visibility();
    // We need to maybe scroll to the selected message
    // once we have the proper viewport set up
    setTimeout(navigate.maybe_scroll_to_selected, 0);
}

const state = {
    is_internal_change: false,
    hash_before_overlay: null,
    old_hash: typeof window !== "undefined" ? window.location.hash : "#",
};

function is_overlay_hash(hash) {
    // Hash changes within this list are overlays and should not unnarrow (etc.)
    const overlay_list = [
        "streams",
        "drafts",
        "settings",
        "organization",
        "invite",
        "keyboard-shortcuts",
        "message-formatting",
        "search-operators",
    ];
    const main_hash = hash_util.get_hash_category(hash);

    return overlay_list.includes(main_hash);
}

// Returns true if this function performed a narrow
function do_hashchange_normal(from_reload) {
    message_viewport.stop_auto_scrolling();

    // NB: In Firefox, window.location.hash is URI-decoded.
    // Even if the URL bar says #%41%42%43%44, the value here will
    // be #ABCD.
    const hash = window.location.hash.split("/");
    switch (hash[0]) {
        case "#narrow": {
            maybe_hide_recent_topics();
            ui_util.change_tab_to("#message_feed_container");
            const operators = hash_util.parse_narrow(hash);
            if (operators === undefined) {
                // If the narrow URL didn't parse, clear
                // window.location.hash and send them to the home tab
                set_hash("");
                activate_home_tab();
                return false;
            }
            const narrow_opts = {
                change_hash: false, // already set
                trigger: "hash change",
            };
            if (from_reload) {
                blueslip.debug("We are narrowing as part of a reload.");
                if (page_params.initial_narrow_pointer !== undefined) {
                    home_msg_list.pre_narrow_offset = page_params.initial_offset;
                    narrow_opts.then_select_id = page_params.initial_narrow_pointer;
                    narrow_opts.then_select_offset = page_params.initial_narrow_offset;
                }
            }
            narrow.activate(operators, narrow_opts);
            floating_recipient_bar.update();
            return true;
        }
        case "":
        case "#":
            activate_home_tab();
            break;
        case "#keyboard-shortcuts":
        case "#message-formatting":
        case "#search-operators":
        case "#recent_topics":
            recent_topics.show();
            break;
        case "#drafts":
        case "#invite":
        case "#streams":
        case "#organization":
        case "#settings":
            blueslip.error("overlay logic skipped for: " + hash);
            break;
    }
    return false;
}

function do_hashchange_overlay(old_hash) {
    const base = hash_util.get_hash_category(window.location.hash);
    const old_base = hash_util.get_hash_category(old_hash);
    const section = hash_util.get_hash_section(window.location.hash);

    const coming_from_overlay = is_overlay_hash(old_hash || "#");

    // Start by handling the specific case of going
    // from something like streams/all to streams_subscribed.
    //
    // In most situations we skip by this logic and load
    // the new overlay.
    if (coming_from_overlay) {
        if (base === old_base) {
            if (base === "streams") {
                subs.change_state(section);
                return;
            }

            if (base === "settings") {
                if (!section) {
                    // We may be on a really old browser or somebody
                    // hand-typed a hash.
                    blueslip.warn("missing section for settings");
                }
                settings_panel_menu.normal_settings.activate_section_or_default(section);
                return;
            }

            if (base === "organization") {
                if (!section) {
                    // We may be on a really old browser or somebody
                    // hand-typed a hash.
                    blueslip.warn("missing section for organization");
                }
                settings_panel_menu.org_settings.activate_section_or_default(section);
                return;
            }

            // TODO: handle other cases like internal settings
            //       changes.
            return;
        }
    }

    // It's not super likely that an overlay is already open,
    // but you can jump from /settings to /streams by using
    // the browser's history menu or hand-editing the URL or
    // whatever.  If so, just close the overlays.
    if (base !== old_base) {
        overlays.close_for_hash_change();
    }

    // NORMAL FLOW: basically, launch the overlay:

    if (!coming_from_overlay) {
        state.hash_before_overlay = old_hash;
    }

    if (base === "streams") {
        subs.launch(section);
        return;
    }

    if (base === "drafts") {
        drafts.launch();
        return;
    }

    if (base === "settings") {
        settings.launch(section);
        return;
    }

    if (base === "organization") {
        admin.launch(section);
        return;
    }

    if (base === "invite") {
        invite.launch();
        return;
    }

    if (base === "keyboard-shortcuts") {
        info_overlay.show("keyboard-shortcuts");
        return;
    }

    if (base === "message-formatting") {
        info_overlay.show("message-formatting");
        return;
    }

    if (base === "search-operators") {
        info_overlay.show("search-operators");
        return;
    }
}

function hashchanged(from_reload, e) {
    const old_hash = e && (e.oldURL ? new URL(e.oldURL).hash : state.old_hash);
    state.old_hash = window.location.hash;

    if (state.is_internal_change) {
        state.is_internal_change = false;
        return undefined;
    }

    if (is_overlay_hash(window.location.hash)) {
        do_hashchange_overlay(old_hash);
        return undefined;
    }

    // We are changing to a "main screen" view.
    overlays.close_for_hash_change();
    changing_hash = true;
    const ret = do_hashchange_normal(from_reload);
    changing_hash = false;
    return ret;
}

exports.update_browser_history = function (new_hash) {
    const old_hash = window.location.hash;

    if (!new_hash.startsWith("#")) {
        blueslip.error("programming error: prefix hashes with #: " + new_hash);
        return;
    }

    if (old_hash === new_hash) {
        // If somebody is calling us with the same hash we already have, it's
        // probably harmless, and we just ignore it.  But it could be a symptom
        // of disorganized code that's prone to an infinite loop of repeatedly
        // assigning the same hash.
        blueslip.info("ignoring probably-harmless call to update_browser_history: " + new_hash);
        return;
    }

    state.old_hash = old_hash;
    state.is_internal_change = true;
    window.location.hash = new_hash;
};

exports.replace_hash = function (hash) {
    if (!window.history.replaceState) {
        // We may have strange behavior with the back button.
        blueslip.warn("browser does not support replaceState");
        return;
    }

    const url = get_full_url(hash);
    window.history.replaceState(null, null, url);
};

exports.go_to_location = function (hash) {
    // Call this function when you WANT the hashchanged
    // function to run.
    window.location.hash = hash;
};

exports.initialize = function () {
    $(window).on("hashchange", (e) => {
        hashchanged(false, e.originalEvent);
    });
    hashchanged(true);
};

exports.exit_overlay = function (callback) {
    if (is_overlay_hash(window.location.hash)) {
        ui_util.blur_active_element();
        const new_hash = state.hash_before_overlay || "#";
        exports.update_browser_history(new_hash);
        if (typeof callback === "function") {
            callback();
        }
    }
};

window.hashchange = exports;
