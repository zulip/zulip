import $ from "jquery";

import {realm_user_settings_defaults} from "./realm_user_settings_defaults";
import * as settings_display from "./settings_display";

export function set_up() {
    const container = $("#realm-user-default-settings");
    settings_display.set_up(container, realm_user_settings_defaults, true);
}
