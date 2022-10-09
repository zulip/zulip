import * as user_group_edit from "./user_group_edit";

// This module will handle ui updates logic for group settings,
// and is analogous to stream_ui_updates.js for stream settings.
export function update_toggler_for_group_setting() {
    user_group_edit.toggler.goto(user_group_edit.select_tab);
}
