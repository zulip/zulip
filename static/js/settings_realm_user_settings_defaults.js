import $ from "jquery";

import {page_params} from "./page_params";
import {realm_user_settings_defaults} from "./realm_user_settings_defaults";
import * as settings_display from "./settings_display";

export function maybe_disable_widgets() {
    if (!page_params.is_admin) {
        $(".organization-box [data-name='organization-level-user-defaults']")
            .find("input, select")
            .prop("disabled", true);

        $(".organization-box [data-name='organization-level-user-defaults']")
            .find(".play_notification_sound")
            .addClass("control-label-disabled");
    }
}
export function set_up() {
    const container = $("#realm-user-default-settings");
    settings_display.set_up(container, realm_user_settings_defaults, true);
    maybe_disable_widgets();
}
