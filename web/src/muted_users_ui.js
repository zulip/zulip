import render_confirm_mute_user from "../templates/confirm_dialog/confirm_mute_user.hbs";

import * as activity from "./activity";
import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import {$t_html} from "./i18n";
import * as inbox_ui from "./inbox_ui";
import * as message_lists from "./message_lists";
import * as muted_users from "./muted_users";
import * as overlays from "./overlays";
import * as people from "./people";
import * as pm_list from "./pm_list";
import * as popovers from "./popovers";
import * as recent_view_ui from "./recent_view_ui";
import * as settings_muted_users from "./settings_muted_users";

export function mute_user(user_id) {
    channel.post({
        url: "/json/users/me/muted_users/" + user_id,
    });
}

export function confirm_mute_user(user_id) {
    function on_click() {
        mute_user(user_id);
    }

    const html_body = render_confirm_mute_user({
        user_name: people.get_full_name(user_id),
    });

    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Mute user"}),
        help_link: "/help/mute-a-user",
        html_body,
        on_click,
    });
}

export function unmute_user(user_id) {
    channel.del({
        url: "/json/users/me/muted_users/" + user_id,
    });
}

export function rerender_for_muted_user() {
    message_lists.current.update_muting_and_rerender();
    if (message_lists.current !== message_lists.home) {
        message_lists.home.update_muting_and_rerender();
    }

    if (overlays.settings_open() && settings_muted_users.loaded) {
        settings_muted_users.populate_list();
    }

    activity.redraw();
    pm_list.update_private_messages();

    // If a user is (un)muted, we want to update their avatars on the Recent Conversations
    // participants column.
    recent_view_ui.complete_rerender();
    inbox_ui.update();
}

export function handle_user_updates(muted_user_ids) {
    popovers.hide_all();
    muted_users.set_muted_users(muted_user_ids);
    rerender_for_muted_user();
}
