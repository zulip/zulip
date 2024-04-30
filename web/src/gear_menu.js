import $ from "jquery";
import WinChan from "winchan";

import render_gear_menu_popover from "../templates/gear_menu_popover.hbs";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as dark_theme from "./dark_theme";
import * as message_lists from "./message_lists";
import * as popover_menus from "./popover_menus";
import * as popover_menus_data from "./popover_menus_data";
import * as popovers from "./popovers";
import * as settings_preferences from "./settings_preferences";
import {parse_html} from "./ui_util";

/*
For various historical reasons there isn't one
single chunk of code that really makes our gear
menu function.  In this comment I try to help
you know where to look for relevant code.

The module that you're reading now doesn't
actually do much of the work.

Our gear menu has these choices:

=================
hash:  Channel settings
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

The menu items get built in a handlebars template
called gear_menu_popover.hbs.

The menu itself has the selector
"settings-dropdown".

The items with the prefix of "hash:" are in-page
links:

    #channels
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
in web/src/info_overlay.ts.  They are dispatched
using a click handler in web/src/click_handlers.js.
The click handler uses "[data-overlay-trigger]" as
the selector and then calls browser_history.go_to_location.
*/

function render(instance) {
    const rendered_gear_menu = render_gear_menu_popover(
        popover_menus_data.get_gear_menu_content_context(),
    );
    instance.setContent(parse_html(rendered_gear_menu));
}

export function initialize() {
    popover_menus.register_popover_menu("#gear-menu", {
        theme: "popover-menu",
        placement: "bottom",
        offset: [-50, 0],
        popperOptions: {
            strategy: "fixed",
            modifiers: [
                {
                    name: "eventListeners",
                    options: {
                        scroll: false,
                    },
                },
            ],
        },
        onMount(instance) {
            const $popper = $(instance.popper);
            popover_menus.popover_instances.gear_menu = instance;
            $popper.on("click", ".webathena_login", (e) => {
                $("#zephyr-mirror-error").removeClass("show");
                const principal = ["zephyr", "zephyr"];
                WinChan.open(
                    {
                        url: "https://webathena.mit.edu/#!request_ticket_v1",
                        relay_url: "https://webathena.mit.edu/relay.html",
                        params: {
                            realm: "ATHENA.MIT.EDU",
                            principal,
                        },
                    },
                    (err, r) => {
                        if (err) {
                            blueslip.warn(err);
                            return;
                        }
                        if (r.status !== "OK") {
                            blueslip.warn(r);
                            return;
                        }

                        channel.post({
                            url: "/accounts/webathena_kerberos_login/",
                            data: {cred: JSON.stringify(r.session)},
                            success() {
                                $("#zephyr-mirror-error").removeClass("show");
                            },
                            error() {
                                $("#zephyr-mirror-error").addClass("show");
                            },
                        });
                    },
                );
                popover_menus.hide_current_popover_if_visible(instance);
                e.preventDefault();
                e.stopPropagation();
            });

            $popper.on("click", ".change-language-spectator", (e) => {
                popover_menus.hide_current_popover_if_visible(instance);
                e.preventDefault();
                e.stopPropagation();
                settings_preferences.launch_default_language_setting_modal();
            });

            // We cannot update recipient bar color using dark_theme.enable/disable due to
            // it being called before message lists are initialized and the order cannot be changed.
            // Also, since these buttons are only visible for spectators which doesn't have events,
            // if theme is changed in a different tab, the theme of this tab remains the same.
            $popper.on("click", "#gear-menu-dropdown .gear-menu-select-dark-theme", (e) => {
                popover_menus.hide_current_popover_if_visible(instance);
                e.preventDefault();
                e.stopPropagation();
                requestAnimationFrame(() => {
                    dark_theme.enable();
                    message_lists.update_recipient_bar_background_color();
                });
            });

            $popper.on("click", "#gear-menu-dropdown .gear-menu-select-light-theme", (e) => {
                popover_menus.hide_current_popover_if_visible(instance);
                e.preventDefault();
                e.stopPropagation();
                requestAnimationFrame(() => {
                    dark_theme.disable();
                    message_lists.update_recipient_bar_background_color();
                });
            });
        },
        onShow: render,
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.gear_menu = undefined;
        },
    });
}

export function toggle() {
    if (popover_menus.is_gear_menu_popover_displayed()) {
        popovers.hide_all();
        return;
    }

    // Since this can be called via hotkey, we need to
    // hide any other popovers that may be open before.
    if (popovers.any_active()) {
        popovers.hide_all();
    }

    $("#gear-menu").trigger("click");
}

export function rerender() {
    if (popover_menus.is_gear_menu_popover_displayed()) {
        render(popover_menus.get_gear_menu_instance());
    }
}
