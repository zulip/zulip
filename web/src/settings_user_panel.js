import $ from "jquery";

import render_user_panel from "../templates/settings/user_panel_admin.hbs";

import * as components from "./components";
import {$t} from "./i18n";
import * as settings_sections from "./settings_sections";
import * as settings_users from "./settings_users";

export function set_up() {
    const user_section_toggler = components.toggle({
        values: [
            {label: $t({defaultMessage: "Users"}), key: "user-list-admin"},
            {label: $t({defaultMessage: "Invitations"}), key: "invites-list-admin"},
            {label: $t({defaultMessage: "Deactivated users"}), key: "deactivated-users-admin"},
        ],
        html_class: "toggle-user-panel",
        callback(_value, key) {
            activate_user_section(key);
        },
    });

    $(".list-toggler-container").prepend(user_section_toggler.get());
    render_user_panel({
        allow_sorting_deactivated_users_list_by_email:
            settings_users.allow_sorting_deactivated_users_list_by_email(),
    });
    activate_user_section("user-list-admin");
}

let $curr_panel;

function activate_user_section(key) {
    const section = key;
    const sel = `[data-name='${CSS.escape(section)}']`;
    const $panel = $(".settings-section" + sel);

    if ($panel !== $curr_panel) {
        if ($curr_panel) {
            $curr_panel.removeClass("show");
        }
        settings_sections.load_settings_section(section);
        $panel.addClass("show");
        $curr_panel = $panel;
    }
}
