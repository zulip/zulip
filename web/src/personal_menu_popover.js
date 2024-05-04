import $ from "jquery";
import tippy from "tippy.js";

import render_personal_menu from "../templates/personal_menu.hbs";

import * as channel from "./channel";
import * as narrow from "./narrow";
import * as people from "./people";
import * as popover_menus from "./popover_menus";
import * as popover_menus_data from "./popover_menus_data";
import * as popovers from "./popovers";
import {current_user} from "./state_data";
import {parse_html} from "./ui_util";
import {user_settings} from "./user_settings";
import * as user_status from "./user_status";

export function initialize() {
    popover_menus.register_popover_menu("#personal-menu", {
        theme: "popover-menu",
        placement: "bottom",
        offset: [-50, 0],
        // The strategy: "fixed"; and eventlisteners modifier option
        // ensure that the personal menu does not modify its position
        // or disappear when user zooms the page.
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
            popover_menus.popover_instances.personal_menu = instance;

            tippy(".personal-menu-clear-status", {
                placement: "top",
                appendTo: document.body,
            });

            $popper.on("change", "input[name='theme-select']", (e) => {
                const new_theme_code = $(e.currentTarget).attr("data-theme-code");
                channel.patch({
                    url: "/json/settings",
                    data: {color_scheme: new_theme_code},
                    error() {
                        // NOTE: The additional delay allows us to visually communicate
                        // that an error occurred due to which we are reverting back
                        // to the previously used value.
                        setTimeout(() => {
                            const prev_theme_code = user_settings.color_scheme;
                            $(e.currentTarget)
                                .parent()
                                .find(`input[data-theme-code="${prev_theme_code}"]`)
                                .prop("checked", true);
                        }, 500);
                    },
                });
            });

            $popper.one("click", ".personal-menu-clear-status", (e) => {
                e.preventDefault();
                const me = current_user.user_id;
                user_status.server_update_status({
                    user_id: me,
                    status_text: "",
                    emoji_name: "",
                    emoji_code: "",
                    success() {
                        popover_menus.hide_current_popover_if_visible(instance);
                    },
                });
            });

            $popper.one("click", ".narrow-self-direct-message", (e) => {
                const user_id = current_user.user_id;
                const email = people.get_by_user_id(user_id).email;
                narrow.by("dm", email, {trigger: "personal menu"});
                popovers.hide_all();
                e.preventDefault();
            });

            $popper.one("click", ".narrow-messages-sent", (e) => {
                const user_id = current_user.user_id;
                const email = people.get_by_user_id(user_id).email;
                narrow.by("sender", email, {trigger: "personal menu"});
                popovers.hide_all();
                e.preventDefault();
            });

            $popper.one("click", ".open-profile-settings", (e) => {
                e.currentTarget.click();
                popovers.hide_all();
                e.preventDefault();
            });
            instance.popperInstance.update();
        },
        onShow(instance) {
            const args = popover_menus_data.get_personal_menu_content_context();
            instance.setContent(parse_html(render_personal_menu(args)));
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.personal_menu = undefined;
        },
    });
}

export function toggle() {
    // NOTE: Since to open personal menu, you need to click on your avatar (which calls
    // tippyjs.hideAll()), or go via gear menu if using hotkeys, we don't need to
    // call tippyjs.hideAll() for it.
    $("#personal-menu").trigger("click");
}
