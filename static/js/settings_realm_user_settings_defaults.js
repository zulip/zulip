import $ from "jquery";

import * as channel from "./channel";
import {page_params} from "./page_params";
import {realm_user_settings_defaults} from "./realm_user_settings_defaults";
import * as settings_display from "./settings_display";
import * as settings_notifications from "./settings_notifications";
import * as settings_ui from "./settings_ui";

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
    settings_notifications.set_up(container, realm_user_settings_defaults, true);

    container.find(".presence_enabled").on("change", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const data = {presence_enabled: container.find(".presence_enabled").prop("checked")};
        settings_ui.do_settings_change(
            channel.patch,
            "/json/realm/user_settings_defaults",
            data,
            container.find(".privacy-setting-status").expectOne(),
        );
    });

    maybe_disable_widgets();
}
