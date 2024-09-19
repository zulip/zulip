import $ from "jquery";

import * as about_zulip from "./about_zulip.ts";
import * as admin from "./admin.js";
import * as blueslip from "./blueslip.ts";
import * as browser_history from "./browser_history.ts";
import * as drafts_overlay_ui from "./drafts_overlay_ui.js";
import * as hash_parser from "./hash_parser.ts";
import * as hash_util from "./hash_util.ts";
import {$t_html} from "./i18n.ts";
import * as inbox_ui from "./inbox_ui.ts";
import * as inbox_util from "./inbox_util.ts";
import * as info_overlay from "./info_overlay.ts";
import * as message_fetch from "./message_fetch.ts";
import * as message_view from "./message_view.ts";
import * as message_viewport from "./message_viewport.ts";
import * as modals from "./modals.ts";
import * as overlays from "./overlays.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import * as popovers from "./popovers.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import * as recent_view_util from "./recent_view_util.ts";
import * as scheduled_messages_overlay_ui from "./scheduled_messages_overlay_ui.ts";
import * as settings from "./settings.js";
import * as settings_panel_menu from "./settings_panel_menu.ts";
import * as settings_toggle from "./settings_toggle.js";
import * as sidebar_ui from "./sidebar_ui.ts";
import * as spectators from "./spectators.ts";
import {current_user} from "./state_data.ts";
import * as stream_settings_ui from "./stream_settings_ui.ts";
import * as ui_report from "./ui_report.ts";
import * as user_group_edit from "./user_group_edit.js";
import * as user_profile from "./user_profile.ts";
import {user_settings} from "./user_settings.ts";

// Read https://zulip.readthedocs.io/en/latest/subsystems/hashchange-system.html
// or locally: docs/subsystems/hashchange-system.md

function maybe_hide_recent_view() {
    if (recent_view_util.is_visible()) {
        recent_view_ui.hide();
        return true;
    }
    return false;
}

function maybe_hide_inbox() {
    if (inbox_util.is_visible()) {
        inbox_ui.hide();
        return true;
    }
    return false;
}

function show_all_message_view() {
    // Don't export this function outside of this module since
    // `change_hash` is false here which means it is should only
    // be called after hash is updated in the URL.
    message_view.show([{operator: "in", operand: "home"}], {
        trigger: "hashchange",
        change_hash: false,
        then_select_id: window.history.state?.narrow_pointer,
        then_select_offset: window.history.state?.narrow_offset,
    });
}

function is_somebody_else_profile_open() {
    return (
        user_profile.get_user_id_if_user_profile_modal_open() !== undefined &&
        user_profile.get_user_id_if_user_profile_modal_open() !== people.my_current_user_id()
    );
}

function handle_invalid_section_url(section, settings_tab) {
    const valid_tab_values = {
        users: new Set(["active", "deactivated", "invitations"]),
        bots: new Set(["all-bots", "your-bots"]),
    };

    if (section === "bots" || section === "users") {
        if (!valid_tab_values[section].has(settings_tab)) {
            const valid_section_url = `#organization/${section}/${[...valid_tab_values[section]][0]}`;
            browser_history.update(valid_section_url);
            return [...valid_tab_values[section]][0];
        }
        return settings_tab;
    }
    return undefined;
}

function get_settings_tab(section) {
    const current_tab = hash_parser.get_current_nth_hash_section(2);
    return handle_invalid_section_url(section, current_tab);
}

export function set_hash_to_home_view(triggered_by_escape_key = false) {
    if (browser_history.is_current_hash_home_view()) {
        return;
    }

    const hash_before_current = browser_history.old_hash();
    if (
        triggered_by_escape_key &&
        browser_history.get_home_view_hash() === "#feed" &&
        (hash_before_current === "" || hash_before_current === "#feed")
    ) {
        // If the previous view was the user's Combined Feed home
        // view, and this change was triggered by escape keypress,
        // then we simulate the back button in order to reuse
        // existing code for restoring the user's scroll position.
        window.history.back();
        return;
    }

    // We want to set URL with no hash here. It is not possible
    // to do so with `window.location.hash` since it will set an empty
    // hash. So, we use `pushState` which simply updates the current URL
    // but doesn't trigger `hashchange`. So, we trigger hashchange directly
    // here to let it handle the whole rendering process for us.
    browser_history.set_hash("");
    hashchanged(false);
}

function show_home_view() {
    // This function should only be called from the hashchange
    // handlers, as it does not set the hash to "".
    //
    // We only allow the primary recommended options for home views
    // rendered without a hash.
    switch (user_settings.web_home_view) {
        case "recent_topics": {
            maybe_hide_inbox();
            recent_view_ui.show();
            break;
        }
        case "all_messages": {
            // Hides inbox/recent views internally if open.
            show_all_message_view();
            break;
        }
        case "inbox": {
            maybe_hide_recent_view();
            inbox_ui.show();
            break;
        }
        default: {
            // NOTE: Setting a hash which is not rendered on
            // empty hash (like a stream narrow) will
            // introduce a bug that user will not be able to
            // go back in browser history. See
            // https://chat.zulip.org/#narrow/channel/9-issues/topic/Browser.20back.20button.20on.20RT
            // for detailed description of the issue.
            window.location.hash = user_settings.web_home_view;
        }
    }
}

// Returns true if this function performed a narrow
function do_hashchange_normal(from_reload, restore_selected_id) {
    message_viewport.stop_auto_scrolling();

    // NB: In Firefox, window.location.hash is URI-decoded.
    // Even if the URL bar says #%41%42%43%44, the value here will
    // be #ABCD.
    const hash = window.location.hash.split("/");

    switch (hash[0]) {
        case "#narrow": {
            let terms;
            try {
                // TODO: Show possible valid URLs to the user.
                terms = hash_util.parse_narrow(hash);
            } catch {
                ui_report.error(
                    $t_html({defaultMessage: "Invalid URL"}),
                    undefined,
                    $("#home-error"),
                    2000,
                );
            }
            if (terms === undefined) {
                // If the narrow URL didn't parse,
                // send them to web_home_view.
                // We cannot clear hash here since
                // it will block user from going back
                // in browser history.
                show_home_view();
                return false;
            }
            const narrow_opts = {
                change_hash: false, // already set
                trigger: "hash change",
                show_more_topics: false,
            };
            if (from_reload) {
                blueslip.debug("We are narrowing as part of a reload.");
                if (message_fetch.initial_narrow_pointer !== undefined) {
                    narrow_opts.then_select_id = message_fetch.initial_narrow_pointer;
                    narrow_opts.then_select_offset = message_fetch.initial_narrow_offset;
                }
            }

            const data_for_hash = window.history.state;
            if (restore_selected_id && data_for_hash) {
                narrow_opts.then_select_id = data_for_hash.narrow_pointer;
                narrow_opts.then_select_offset = data_for_hash.narrow_offset;
                narrow_opts.show_more_topics = data_for_hash.show_more_topics ?? false;
            }
            message_view.show(terms, narrow_opts);
            return true;
        }
        case "":
        case "#":
            show_home_view();
            break;
        case "#recent_topics":
            // The URL for Recent Conversations was changed from
            // #recent_topics to #recent in 2022. Because pre-change
            // Welcome Bot messages included links to this URL, we
            // need to support the "#recent_topics" hash as an alias
            // for #recent permanently. We show the view and then
            // replace the current URL hash in a way designed to hide
            // this detail in the browser's forward/back session history.
            recent_view_ui.show();
            window.location.replace("#recent");
            break;
        case "#recent":
            maybe_hide_inbox();
            recent_view_ui.show();
            break;
        case "#inbox":
            maybe_hide_recent_view();
            inbox_ui.show();
            break;
        case "#all_messages":
            // "#all_messages" was renamed to "#feed" in 2024. Unlike
            // the recent hash rename, there are likely few links that
            // would break if this compatibility code was removed, but
            // there's little cost to keeping it.
            show_all_message_view();
            window.location.replace("#feed");
            break;
        case "#feed":
            show_all_message_view();
            break;
        case "#keyboard-shortcuts":
        case "#message-formatting":
        case "#search-operators":
        case "#drafts":
        case "#invite":
        case "#channels":
        case "#streams":
        case "#organization":
        case "#settings":
        case "#about-zulip":
        case "#scheduled":
            blueslip.error("overlay logic skipped for: " + hash);
            break;
        default:
            show_home_view();
    }
    return false;
}

function do_hashchange_overlay(old_hash) {
    if (old_hash === undefined) {
        // The user opened the app with an overlay hash; we need to
        // show the user's home view behind it.
        show_home_view();
    }
    let base = hash_parser.get_current_hash_category();
    const old_base = hash_parser.get_hash_category(old_hash);
    let section = hash_parser.get_current_hash_section();

    if (base === "groups" && current_user.is_guest) {
        // The #groups settings page is unfinished, and disabled in production.
        show_home_view();
        return;
    }

    const coming_from_overlay = hash_parser.is_overlay_hash(old_hash);
    if (section === "display-settings") {
        // Since display-settings was deprecated and replaced with preferences
        // #settings/display-settings is being redirected to #settings/preferences.
        section = "preferences";
    }
    if (section === "bot-list-admin") {
        // #organization/bot-list-admin is being redirected to #organization/bots.
        section = "bots";
        base = "organization";
    }
    if (section === "user-list-admin") {
        // #settings/user-list-admin is being redirected to #settings/users after it was renamed.
        section = "users";
    }

    if (section === "your-bots") {
        // #settings/your-bots is being redirected to #organization/bots/your-bots.
        section = "bots";
        base = "organization";
        window.history.replaceState(null, "", "#organization/bots/your-bots");
    }

    if ((base === "settings" || base === "organization") && !section) {
        let settings_panel_object = settings_panel_menu.normal_settings;
        if (base === "organization") {
            settings_panel_object = settings_panel_menu.org_settings;
        }
        window.history.replaceState(
            null,
            "",
            browser_history.get_full_url(base + "/" + settings_panel_object.current_tab),
        );
    }

    // In 2024, stream was renamed to channel in the Zulip API and UI.
    // Because pre-change Welcome Bot and Notification Bot messages
    // included links to "/#streams/all" and "/#streams/new", we'll
    // need to support "streams" as an overlay hash as an alias for
    // "channels" permanently.
    if (base === "streams" || base === "channels") {
        const valid_hash = hash_util.validate_channels_settings_hash(window.location.hash);
        // Here valid_hash will always return "channels" as the base.
        // So, if we update the history because the valid hash does
        // not match the window.location.hash, then we also reset the
        // base string we're tracking for the hash.
        if (valid_hash !== window.location.hash) {
            window.history.replaceState(null, "", browser_history.get_full_url(valid_hash));
            section = hash_parser.get_current_hash_section();
            base = hash_parser.get_current_hash_category();
        }
    }

    if (base === "groups") {
        const valid_hash = hash_util.validate_group_settings_hash(window.location.hash);
        if (valid_hash !== window.location.hash) {
            window.history.replaceState(null, "", browser_history.get_full_url(valid_hash));
            section = hash_parser.get_current_hash_section();
        }
    }

    // Start by handling the specific case of going from
    // something like "#channels/all" to "#channels/subscribed".
    //
    // In most situations we skip by this logic and load
    // the new overlay.
    if (coming_from_overlay && base === old_base) {
        if (base === "channels") {
            // e.g. #channels/29/social/subscribers
            const right_side_tab = hash_parser.get_current_nth_hash_section(3);
            stream_settings_ui.change_state(section, undefined, right_side_tab);
            return;
        }

        if (base === "groups") {
            const right_side_tab = hash_parser.get_current_nth_hash_section(3);
            user_group_edit.change_state(section, undefined, right_side_tab);
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
            settings_panel_menu.org_settings.activate_section_or_default(
                section,
                get_settings_tab(section),
            );

            settings_panel_menu.org_settings.activate_section_or_default(
                section,
                section === "bots" && window.location.hash.includes("your-bots")
                    ? "your-bots"
                    : get_settings_tab(section),
            );

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
            settings_panel_menu.normal_settings.set_current_tab(section);
        } else {
            settings_panel_menu.org_settings.set_current_tab(section);
            if (section === "users") {
                settings_panel_menu.org_settings.set_user_settings_tab(get_settings_tab(section));
            } else {
                settings_panel_menu.org_settings.set_bot_settings_tab(get_settings_tab(section));
            }
        }
        settings_toggle.goto(base);
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

    if (base === "channels") {
        // e.g. #channels/29/social/subscribers
        const right_side_tab = hash_parser.get_current_nth_hash_section(3);

        if (is_somebody_else_profile_open()) {
            stream_settings_ui.launch(section, "all-streams", right_side_tab);
            return;
        }

        // We pass left_side_tab as undefined in change_state to
        // select the tab based on user's subscriptions. "Subscribed" is
        // selected if user is subscribed to the stream being edited.
        // Otherwise "All streams" is selected.
        stream_settings_ui.launch(section, undefined, right_side_tab);
        return;
    }

    if (base === "groups") {
        const right_side_tab = hash_parser.get_current_nth_hash_section(3);

        if (is_somebody_else_profile_open()) {
            user_group_edit.launch(section, "all-groups", right_side_tab);
            return;
        }

        // We pass left_side_tab as undefined in change_state to
        // select the tab based on user's membership. "My groups" is
        // selected if user is a member of group being edited.
        // Otherwise "All groups" is selected.
        user_group_edit.launch(section, undefined, right_side_tab);
        return;
    }

    if (base === "drafts") {
        drafts_overlay_ui.launch();
        return;
    }

    if (base === "settings") {
        settings.build_page();
        admin.build_page();
        settings.launch(section);
        return;
    }

    if (base === "organization") {
        settings.build_page();
        admin.build_page();
        if (section === "users") {
            admin.launch(section, get_settings_tab(section));
        } else {
            admin.launch(
                section,
                section === "bots" && window.location.hash.includes("your-bots")
                    ? "your-bots"
                    : get_settings_tab(section),
            );
        }
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

    if (base === "scheduled") {
        scheduled_messages_overlay_ui.launch();
    }
    if (base === "user") {
        const user_id = Number.parseInt(hash_parser.get_current_hash_section(), 10);
        if (!people.is_known_user_id(user_id)) {
            user_profile.show_user_profile_access_error_modal();
        } else {
            const user = people.get_by_user_id(user_id);
            user_profile.show_user_profile(user);
        }
    }
}

function hashchanged(from_reload, e, restore_selected_id = true) {
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

    popovers.hide_all();

    if (hash_parser.is_overlay_hash(current_hash)) {
        browser_history.state.changing_hash = true;
        modals.close_active_if_any();
        do_hashchange_overlay(old_hash);
        browser_history.state.changing_hash = false;
        return undefined;
    }

    // We are changing to a "main screen" view.
    overlays.close_for_hash_change();
    sidebar_ui.hide_all();
    modals.close_active_if_any();
    browser_history.state.changing_hash = true;
    const ret = do_hashchange_normal(from_reload, restore_selected_id);
    browser_history.state.changing_hash = false;
    return ret;
}

export function initialize() {
    // We don't want browser to restore the scroll
    // position of the new hash in the current hash.
    window.history.scrollRestoration = "manual";

    $(window).on("hashchange", (e) => {
        hashchanged(false, e.originalEvent);
    });
    hashchanged(true);

    $("body").on("click", "a", (e) => {
        const href = e.currentTarget.getAttribute("href");
        if (href === window.location.hash && href.includes("/near/")) {
            // The clicked on a link, perhaps a "said" reference, that
            // matches the current view. Such a click doesn't trigger
            // a hashchange event, so we manually trigger one in order
            // to ensure the app scrolls to the correct message.
            hashchanged(false, e, false);
        }
    });
}
