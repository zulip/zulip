import $ from "jquery";

import render_gear_menu from "../templates/gear_menu.hbs";

import * as popover_menus_data from "./popover_menus_data";

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

export function initialize() {
    const rendered_gear_menu = render_gear_menu(popover_menus_data.get_gear_menu_content_context());
    $("#navbar-buttons").html(rendered_gear_menu);
}

export function open() {
    $("#settings-dropdown").trigger("click");
    // there are invisible li tabs, which should not be clicked.
    $("#gear-menu").find("li:not(.invisible) a").eq(0).trigger("focus");
}

export function is_open() {
    return $(".dropdown").hasClass("open");
}

export function close() {
    if (is_open()) {
        $(".dropdown").removeClass("open");
    }
}
