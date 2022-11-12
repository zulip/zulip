import $ from "jquery";

import render_personal_menu from "../templates/personal_menu.hbs";

import { page_params } from "./page_params";
import { user_settings } from "./user_settings";
import * as buddy_data from "./buddy_data";
import * as people from "./people";
import * as user_status from "./user_status";

export function initialize() {
    let rendered_personal_menu;
    const is_spectator = page_params.is_spectator;

    if (!is_spectator) {
        const my_user_id = page_params.user_id;
        const invisible_mode = !user_settings.presence_enabled;
        const status_text = user_status.get_status_text(my_user_id);
        const status_emoji_info = user_status.get_status_emoji(my_user_id);

        rendered_personal_menu = render_personal_menu({
            user_id: my_user_id,
            invisible_mode,
            user_is_guest: page_params.is_guest,
            spectator_view: page_params.is_spectator,

            // user information
            user_avatar: page_params.avatar_url_medium,
            is_active: people.is_active_user_for_popover(my_user_id),
            user_circle_class: buddy_data.get_user_circle_class(my_user_id),
            user_last_seen_time_status: buddy_data.user_last_seen_time_status(my_user_id),
            user_full_name: page_params.full_name,
            user_type: people.get_user_type(my_user_id),

            // user status
            status_content_available: Boolean(status_text || status_emoji_info),
            status_text,
            status_emoji_info,
            user_time: people.get_user_time(my_user_id),
        });

        const existElement = document.querySelector("#personal-menu .dropdown-menu");
        if (existElement) {
            existElement.remove();
        }
        document.querySelector("#personal-menu").insertAdjacentHTML('beforeend',rendered_personal_menu);
    }
}

export function close() {
    document.querySelector("#personal-menu").classList.remove("open");
}

export function register_click_handlers() {
    $("body").on("click", "#personal-menu .header-button", (e) => {
        initialize();
    });

    $("body").on("click", "#personal-menu .clear_status", (e) => {
        e.preventDefault();
        const me = page_params.user_id;
        user_status.server_update_status({
            user_id: me,
            status_text: "",
            emoji_name: "",
            emoji_code: ""
        });
        close();
    });

    $("body").on("click", "#personal-menu .invisible_mode_turn_on", (e) => {
        user_status.server_invisible_mode_on();
        e.stopPropagation();
        e.preventDefault();
        close();
    });

    $("body").on("click", "#personal-menu .invisible_mode_turn_off", (e) => {
        user_status.server_invisible_mode_off();
        e.stopPropagation();
        e.preventDefault();
        close();
    });
}
