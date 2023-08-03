import $ from "jquery";

import render_gear_menu from "../templates/gear_menu.hbs";

import {$t} from "./i18n";
import {page_params} from "./page_params";
import * as settings_data from "./settings_data";

/*
For various historical reasons there isn't one
single chunk of code that really makes our gear
menu function.  In this comment I try to help
you know where to look for relevant code.

The module that you're reading now doesn't
actually do much of the work.

Our gear menu has these choices:

=================
hash:  Manage streams
hash:  Settings
hash:  Organization settings
link:  Usage statistics
---
link:  Help center
info:  Keyboard shortcuts
info:  Message formatting
info:  Search filters
hash:  About Zulip
---
link:  Desktop & mobile apps
link:  Integrations
link:  API documentation
link:  Sponsor Zulip
link:  Plans and pricing
---
hash:   Invite users
---
misc:  Logout
=================

Depending on settings, there may also be choices
like "Feedback" or "Debug".

The menu items get built in a server-side template called
templates/zerver/app/navbar.html.  Each item is
an HTML anchor tag with a "role" of "menuitem".

The menu itself has the selector
"settings-dropdown".

The items with the prefix of "hash:" are in-page
links:

    #streams
    #settings
    #organization
    #about-zulip
    #invite

When you click on the links there is a function
called hashchanged() in web/src/hashchange.js
that gets invoked.  (We register this as a listener
for the hashchange event.)  This function then
launches the appropriate modal for each menu item.
Look for things like subs.launch(...) or
invite.launch() in that code.

Some items above are prefixed with "link:".  Those
items, when clicked, just use the normal browser
mechanism to link to external pages, and they
have a target of "_blank".

The "info:" items use our info overlay system
in web/src/info_overlay.js.  They are dispatched
using a click handler in web/src/click_handlers.js.
The click handler uses "[data-overlay-trigger]" as
the selector and then calls browser_history.go_to_location.
*/

export function version_display_string(): string {
    const version = page_params.zulip_version;
    const is_fork = page_params.zulip_merge_base && page_params.zulip_merge_base !== version;

    if (page_params.zulip_version.endsWith("-dev+git")) {
        // The development environment uses this version string format.
        return $t({defaultMessage: "Zulip Server dev environment"});
    }

    if (is_fork) {
        // For forks, we want to describe the Zulip version this was
        // forked from, and that it was modified.
        const display_version = page_params.zulip_merge_base
            .replace(/\+git.*/, "")
            .replace(/-dev.*/, "-dev");
        return $t({defaultMessage: "Zulip Server {display_version} (modified)"}, {display_version});
    }

    // The below cases are all for official versions; either a
    // release, or Git commit from one of Zulip's official branches.

    if (version.includes("+git")) {
        // A version from a Zulip official maintenance branch such as 5.x.
        const display_version = version.replace(/\+git.*/, "");
        return $t({defaultMessage: "Zulip Server {display_version} (patched)"}, {display_version});
    }

    const display_version = version.replace(/\+git.*/, "").replace(/-dev.*/, "-dev");
    return $t({defaultMessage: "Zulip Server {display_version}"}, {display_version});
}

export function initialize(): void {
    const rendered_gear_menu = render_gear_menu({
        realm_name: page_params.realm_name,
        realm_url: new URL(page_params.realm_uri).hostname,
        is_owner: page_params.is_owner,
        is_admin: page_params.is_admin,
        is_self_hosted: page_params.realm_plan_type === 1,
        is_plan_limited: page_params.realm_plan_type === 2,
        is_plan_standard: page_params.realm_plan_type === 3,
        is_plan_standard_sponsored_for_free: page_params.realm_plan_type === 4,
        is_business_org: page_params.realm_org_type === 10,
        is_education_org: page_params.realm_org_type === 30 || page_params.realm_org_type === 35,
        standard_plan_name: "Zulip Cloud Standard",
        server_needs_upgrade: page_params.server_needs_upgrade,
        version_display_string: version_display_string(),
        apps_page_url: page_params.apps_page_url,
        can_create_multiuse_invite: settings_data.user_can_create_multiuse_invite(),
        can_invite_users_by_email: settings_data.user_can_invite_users_by_email(),
        corporate_enabled: page_params.corporate_enabled,
        is_guest: page_params.is_guest,
        login_link: page_params.development_environment ? "/devlogin/" : "/login/",
        promote_sponsoring_zulip: page_params.promote_sponsoring_zulip,
        show_billing: page_params.show_billing,
        show_plans: page_params.show_plans,
        show_webathena: page_params.show_webathena,
    });
    $("#navbar-buttons").html(rendered_gear_menu);
}

export function open(): void {
    $("#settings-dropdown").trigger("click");
    // there are invisible li tabs, which should not be clicked.
    $("#gear-menu").find("li:not(.invisible) a").eq(0).trigger("focus");
}

export function is_open(): boolean {
    return $(".dropdown").hasClass("open");
}

export function close(): void {
    if (is_open()) {
        $(".dropdown").removeClass("open");
    }
}
