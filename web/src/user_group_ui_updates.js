import $ from "jquery";

import {$t} from "./i18n";
import {page_params} from "./page_params";
import * as stream_ui_updates from "./stream_ui_updates";
import * as user_group_edit from "./user_group_edit";

// This module will handle ui updates logic for group settings,
// and is analogous to stream_ui_updates.js for stream settings.
export function update_toggler_for_group_setting() {
    user_group_edit.toggler.goto(user_group_edit.select_tab);
}

export function update_add_members_elements(group) {
    if (!user_group_edit.is_editing_group(group.id)) {
        return;
    }

    // We are only concerned with the Members tab for editing groups.
    const $add_members_container = $(".edit_members_for_user_group .add_subscribers_container");

    if (page_params.is_guest || page_params.realm_is_zephyr_mirror_realm) {
        // For guest users, we just hide the add_members feature.
        $add_members_container.hide();
        return;
    }

    // Otherwise, we adjust whether the widgets are disabled based on
    // whether this user is authorized to add subscribers.
    const $input_element = $add_members_container.find(".input").expectOne();
    const $button_element = $add_members_container
        .find('button[name="add_subscriber"]')
        .expectOne();

    if (user_group_edit.can_edit(group.id)) {
        $input_element.prop("disabled", false);
        $button_element.prop("disabled", false);
        $button_element.css("pointer-events", "");
        $add_members_container[0]._tippy?.destroy();
    } else {
        $input_element.prop("disabled", true);
        $button_element.prop("disabled", true);

        stream_ui_updates.initialize_disable_btn_hint_popover(
            $add_members_container,
            $t({defaultMessage: "Only group members can add users to a group."}),
        );
    }
}
