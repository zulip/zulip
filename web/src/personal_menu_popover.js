import $ from "jquery";
import tippy from "tippy.js";

import render_personal_menu from "../templates/personal_menu.hbs";

import * as gear_menu from "./gear_menu";
import * as narrow from "./narrow";
import {page_params} from "./page_params";
import * as people from "./people";
import * as popover_menus from "./popover_menus";
import * as popover_menus_data from "./popover_menus_data";
import * as popovers from "./popovers";
import {parse_html} from "./ui_util";
import * as user_profile from "./user_profile";
import * as user_status from "./user_status";

function elem_to_user_id($elem) {
    return Number.parseInt($elem.attr("data-user-id"), 10);
}

export function initialize() {
    popover_menus.register_popover_menu("#personal-menu", {
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
            $popper.addClass("personal-menu-tippy");
            popover_menus.popover_instances.personal_menu = instance;

            // Workaround for the gear menu not being a tippy popover
            // and thus not auto-closing.
            gear_menu.close();

            tippy(".clear_status", {
                placement: "top",
                appendTo: document.body,
                interactive: true,
            });

            $popper.one("click", ".clear_status", (e) => {
                e.preventDefault();
                const me = page_params.user_id;
                user_status.server_update_status({
                    user_id: me,
                    status_text: "",
                    emoji_name: "",
                    emoji_code: "",
                    success() {
                        instance.hide();
                    },
                });
            });

            $popper.one("click", ".personal-menu-actions .view_full_user_profile", (e) => {
                const user_id = elem_to_user_id($(e.target).closest(".personal-menu-actions"));
                const user = people.get_by_user_id(user_id);
                popovers.hide_all();
                user_profile.show_user_profile(user);
                e.preventDefault();
            });

            $popper.one("click", ".narrow-self-direct-message", (e) => {
                const user_id = page_params.user_id;
                const email = people.get_by_user_id(user_id).email;
                narrow.by("dm", email, {trigger: "personal menu"});
                popovers.hide_all();
                e.preventDefault();
            });

            $popper.one("click", ".narrow-messages-sent", (e) => {
                const user_id = page_params.user_id;
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

            $(".focus-dropdown").on("focus", (e) => {
                e.preventDefault();
                $popper.find("li:visible a").eq(0).trigger("focus");
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
