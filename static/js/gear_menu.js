"use strict";

/*
For various historical reasons there isn't one
single chunk of code that really makes our gear
menu function.  In this comment I try to help
you know where to look for relevant code.

The module that you're reading now doesn't
actually doesn't do much of the work.

Our gear menu has these choices:

=================
hash:  Manage streams
hash:  Settings
hash:  Organization settings
---
link:  Help center
info:  Keyboard shortcuts
info:  Message formatting
info:  Search operators
---
link:  Desktop & mobile apps
link:  Integrations
link:  API documentation
link:  Statistics
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
    #invite

When you click on the links there is a function
called hashchanged() in static/js/hashchange.js
that gets invoked.  (We use window.onhashchange
to register the handler.)  This function then
launches the appropriate modal for each menu item.
Look for things like subs.launch(...) or
invite.launch() in that code.

Some items above are prefixed with "link:".  Those
items, when clicked, just use the normal browser
mechanism to link to external pages, and they
have a target of "_blank".

The "info:" items use our info overlay system
in static/js/info_overlay.js.  They are dispatched
using a click handler in static/js/click_handlers.js.
The click handler uses "[data-overlay-trigger]" as
the selector and then calls hash_change.go_to_location.

*/

// We want to remember how far we were scrolled on each 'tab'.
// To do so, we need to save away the old position of the
// scrollbar when we switch to a new tab (and restore it
// when we switch back.)
const scroll_positions = new Map();

exports.update_org_settings_menu_item = function () {
    const item = $(".admin-menu-item").expectOne();
    if (page_params.is_admin) {
        item.find("span").text(i18n.t("Manage organization"));
    } else {
        item.find("span").text(i18n.t("Organization settings"));
    }
};

exports.initialize = function () {
    exports.update_org_settings_menu_item();

    $('#gear-menu a[data-toggle="tab"]').on("show", (e) => {
        // Save the position of our old tab away, before we switch
        const old_tab = $(e.relatedTarget).attr("href");
        scroll_positions.set(old_tab, message_viewport.scrollTop());
    });
    $('#gear-menu a[data-toggle="tab"]').on("shown", (e) => {
        const target_tab = $(e.target).attr("href");
        // Hide all our error messages when switching tabs
        $(".alert").removeClass("show");

        // Set the URL bar title to show the sub-page you're currently on.
        let browser_url = target_tab;
        if (browser_url === "#message_feed_container") {
            browser_url = "";
        }
        hashchange.changehash(browser_url);

        // After we show the new tab, restore its old scroll position
        // (we apparently have to do this after setting the hash,
        // because otherwise that action may scroll us somewhere.)
        if (target_tab === "#message_feed_container") {
            if (scroll_positions.has(target_tab)) {
                message_viewport.scrollTop(scroll_positions.get(target_tab));
            } else {
                navigate.scroll_to_selected();
            }
        }
    });

    // The admin and settings pages are generated client-side through
    // templates.
};

exports.open = function () {
    $("#settings-dropdown").trigger("click");
    // there are invisible li tabs, which should not be clicked.
    $("#gear-menu").find("li:not(.invisible) a").eq(0).trigger("focus");
};

exports.is_open = function () {
    return $(".dropdown").hasClass("open");
};

exports.close = function () {
    if (exports.is_open()) {
        $(".dropdown").removeClass("open");
    }
};

window.gear_menu = exports;
