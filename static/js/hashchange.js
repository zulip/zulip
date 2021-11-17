import $ from "jquery";

import * as about_zulip from "./about_zulip";
import * as admin from "./admin";
import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as drafts from "./drafts";
import * as floating_recipient_bar from "./floating_recipient_bar";
import * as hash_util from "./hash_util";
import * as info_overlay from "./info_overlay";
import * as invite from "./invite";
import * as message_lists from "./message_lists";
import * as message_viewport from "./message_viewport";
import * as narrow from "./narrow";
import * as navigate from "./navigate";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as recent_topics_ui from "./recent_topics_ui";
import * as recent_topics_util from "./recent_topics_util";
import * as search from "./search";
import * as settings from "./settings";
import * as settings_panel_menu from "./settings_panel_menu";
import * as settings_toggle from "./settings_toggle";
import * as spectators from "./spectators";
import * as stream_settings_ui from "./stream_settings_ui";
import * as top_left_corner from "./top_left_corner";
import * as ui_util from "./ui_util";
import {user_settings} from "./user_settings";

// Read https://zulip.readthedocs.io/en/latest/subsystems/hashchange-system.html
// or locally: docs/subsystems/hashchange-system.md

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
        browser_history.update_web_public_hash(hash);
    } else {
        blueslip.warn("browser does not support pushState");
        window.location.hash = hash;
    }
}

function maybe_hide_recent_topics() {
    if (recent_topics_util.is_visible()) {
        recent_topics_ui.hide();
        return true;
    }
    return false;
}

export function changehash(newhash) {
    if (browser_history.state.changing_hash) {
        return;
    }
    maybe_hide_recent_topics();
    message_viewport.stop_auto_scrolling();
    set_hash(newhash);
}

export function save_narrow(operators) {
    if (browser_history.state.changing_hash) {
        return;
    }
    const new_hash = hash_util.operators_to_hash(operators);
    changehash(new_hash);
}

function show_all_message_view() {
    const coming_from_recent_topics = maybe_hide_recent_topics();
    ui_util.change_tab_to("#message_feed_container");
    narrow.deactivate(coming_from_recent_topics);
    top_left_corner.handle_narrow_deactivated();
    floating_recipient_bar.update();
    search.update_button_visibility();
    // We need to maybe scroll to the selected message
    // once we have the proper viewport set up
    setTimeout(navigate.maybe_scroll_to_selected, 0);
}

export function set_hash_to_default_view() {
    window.location.hash = "";
}

function show_default_view() {
    // This function should only be called from the hashchange
    // handlers, as it does not set the hash to "".
    //
    // We only allow all_messages and recent_topics
    // to be rendered without a hash.
    if (user_settings.default_view === "recent_topics") {
        recent_topics_ui.show();
    } else if (user_settings.default_view === "all_messages") {
        show_all_message_view();
    } else {
        // NOTE: Setting a hash which is not rendered on
        // empty hash (like a stream narrow) will
        // introduce a bug that user will not be able to
        // go back in browser history. See
        // https://chat.zulip.org/#narrow/stream/9-issues/topic/Browser.20back.20button.20on.20RT
        // for detailed description of the issue.
        window.location.hash = user_settings.default_view;
    }
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
                // If the narrow URL didn't parse,
                // send them to default_view.
                // We cannot clear hash here since
                // it will block user from going back
                // in browser history.
                show_default_view();
                return false;
            }
            const narrow_opts = {
                change_hash: false, // already set
                trigger: "hash change",
            };
            if (from_reload) {
                blueslip.debug("We are narrowing as part of a reload.");
                if (page_params.initial_narrow_pointer !== undefined) {
                    message_lists.home.pre_narrow_offset = page_params.initial_offset;
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
            show_default_view();
            break;
        case "#recent_topics":
            recent_topics_ui.show();
            break;
        case "#all_messages":
            show_all_message_view();
            break;
        case "#keyboard-shortcuts":
        case "#message-formatting":
        case "#search-operators":
        case "#drafts":
        case "#invite":
        case "#streams":
        case "#organization":
        case "#settings":
        case "#about-zulip":
            blueslip.error("overlay logic skipped for: " + hash);
            break;
        default:
            show_default_view();
    }
    return false;
}

function do_hashchange_overlay(old_hash) {
    if (old_hash === undefined) {
        // The user opened the app with an overlay hash; we need to
        // show the user's default view behind it.
        show_default_view();
    }
    const base = hash_util.get_current_hash_category();
    const old_base = hash_util.get_hash_category(old_hash);
    const section = hash_util.get_current_hash_section();

    const coming_from_overlay = hash_util.is_overlay_hash(old_hash || "#");

    // Start by handling the specific case of going
    // from something like streams/all to streams_subscribed.
    //
    // In most situations we skip by this logic and load
    // the new overlay.
    if (coming_from_overlay && base === old_base) {
        if (base === "streams") {
            stream_settings_ui.change_state(section);
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

    // This is a special case when user clicks on a URL that makes the overlay switch
    // from org settings to user settings or user edits the URL to switch between them.
    const settings_hashes = new Set(["settings", "organization"]);
    // Ensure that we are just switching between user and org settings and the settings
    // overlay is open.
    const is_hashchange_internal =
        settings_hashes.has(base) && settings_hashes.has(old_base) && overlays.settings_open();
    if (is_hashchange_internal) {
        if (base === "settings") {
            settings_panel_menu.normal_settings.activate_section_or_default(section);
        } else {
            settings_panel_menu.org_settings.activate_section_or_default(section);
        }
        settings_toggle.highlight_toggle(base);
        return;
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
        browser_history.set_hash_before_overlay(old_hash);
    }

    if (base === "streams") {
        stream_settings_ui.launch(section);
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

    if (base === "about-zulip") {
        about_zulip.launch();
    }
}

function hashchanged(from_reload, e) {
    const current_hash = window.location.hash;
    const old_hash = e && (e.oldURL ? new URL(e.oldURL).hash : browser_history.old_hash());
    const is_hash_web_public_compatible = browser_history.update_web_public_hash(current_hash);

    const was_internal_change = browser_history.save_old_hash();
    if (was_internal_change) {
        return undefined;
    }

    // TODO: Migrate the `#reload` syntax to use slashes as separators
    // so that this can be part of the main switch statement.
    if (window.location.hash.startsWith("#reload")) {
        // We don't want to change narrow if app is undergoing reload.
        return undefined;
    }

    if (page_params.is_spectator && !is_hash_web_public_compatible) {
        spectators.login_to_access();
        return undefined;
    }

    if (hash_util.is_overlay_hash(current_hash)) {
        browser_history.state.changing_hash = true;
        do_hashchange_overlay(old_hash);
        browser_history.state.changing_hash = false;
        return undefined;
    }

    // We are changing to a "main screen" view.
    overlays.close_for_hash_change();
    browser_history.state.changing_hash = true;
    const ret = do_hashchange_normal(from_reload);
    browser_history.state.changing_hash = false;
    return ret;
}

export function initialize() {
    $(window).on("hashchange", (e) => {
        hashchanged(false, e.originalEvent);
    });
    hashchanged(true);
}
