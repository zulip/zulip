import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";
import WinChan from "winchan";
import * as z from "zod/mini";

import render_navbar_gear_menu_popover from "../templates/popovers/navbar/navbar_gear_menu_popover.hbs";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as demo_organizations_ui from "./demo_organizations_ui.ts";
import * as information_density from "./information_density.ts";
import * as popover_menus from "./popover_menus.ts";
import * as popover_menus_data from "./popover_menus_data.ts";
import * as popovers from "./popovers.ts";
import * as settings_preferences from "./settings_preferences.ts";
import * as theme from "./theme.ts";
import {parse_html} from "./ui_util.ts";
import {user_settings} from "./user_settings.ts";

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
called hashchanged() in web/src/hashchange.ts
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
using a click handler in web/src/click_handlers.ts.
The click handler uses "[data-overlay-trigger]" as
the selector and then calls browser_history.go_to_location.
*/

function render(instance: tippy.Instance): void {
    const rendered_gear_menu = render_navbar_gear_menu_popover(
        popover_menus_data.get_gear_menu_content_context(),
    );
    instance.setContent(parse_html(rendered_gear_menu));
    $("#gear-menu").addClass("active-navbar-menu");
}

export function initialize(): void {
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
                    (err, raw_response) => {
                        if (err !== null) {
                            blueslip.warn(err);
                            return;
                        }

                        // https://github.com/davidben/webathena/blob/0be20d9b1d62c19b4f94f77e621bd8721e504446/app/scripts-src/request_ticket.js
                        const response_schema = z.discriminatedUnion("status", [
                            z.object({
                                status: z.literal("OK"),
                                session: z.unknown(),
                            }),
                            z.object({
                                status: z.literal("ERROR"),
                                code: z.string(),
                                message: z.string(),
                            }),
                            z.object({
                                status: z.literal("DENIED"),
                                code: z.string(),
                                message: z.string(),
                            }),
                        ]);
                        const r = response_schema.parse(raw_response);
                        if (r.status !== "OK") {
                            blueslip.warn(`Webathena: ${r.status}: ${r.message}`);
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

            $popper.on("click", ".convert-demo-organization", (e) => {
                popover_menus.hide_current_popover_if_visible(instance);
                e.preventDefault();
                e.stopPropagation();
                demo_organizations_ui.show_convert_demo_organization_modal();
            });

            $popper.on("click", ".change-language-spectator", (e) => {
                popover_menus.hide_current_popover_if_visible(instance);
                e.preventDefault();
                e.stopPropagation();
                settings_preferences.launch_default_language_setting_modal();
            });

            $popper.on("change", "input[name='theme-select']", (e) => {
                const theme_code = Number.parseInt($(e.currentTarget).attr("data-theme-code")!, 10);
                requestAnimationFrame(() => {
                    theme.set_theme_for_spectator(theme_code);
                });
            });

            $popper.on("click", ".info-density-controls button", function (this: HTMLElement, e) {
                const changed_property =
                    information_density.information_density_properties_schema.parse(
                        $(this).closest(".button-group").attr("data-property"),
                    );
                information_density.update_information_density_settings($(this), changed_property);
                information_density.enable_or_disable_control_buttons($popper);

                if (changed_property === "web_font_size_px") {
                    // We do not want to display the arrow once font size is
                    // changed because popover will be detached from the gear
                    // icon as we do not change the font size in popover.
                    $("#gear-menu-dropdown").closest(".tippy-box").find(".tippy-arrow").hide();
                }

                e.preventDefault();
            });

            information_density.enable_or_disable_control_buttons($popper);

            // We do not want font size of the popover to change when changing
            // font size using the buttons in popover, so that the buttons do
            // not shift.
            const font_size =
                popover_menus.POPOVER_FONT_SIZE_IN_EM * user_settings.web_font_size_px;
            $("#gear-menu-dropdown")
                .closest(".tippy-box")
                .css("font-size", font_size + "px");
        },
        onShow: render,
        onHidden(instance) {
            $("#gear-menu").removeClass("active-navbar-menu");
            instance.destroy();
            popover_menus.popover_instances.gear_menu = null;
        },
    });
}

export function toggle(): void {
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

export function rerender(): void {
    if (popover_menus.is_gear_menu_popover_displayed()) {
        const instance = popover_menus.get_gear_menu_instance();
        assert(instance !== null);
        render(instance);
    }
}
