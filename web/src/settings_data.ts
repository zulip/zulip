import {page_params} from "./page_params";
import * as settings_config from "./settings_config";
import {current_user, realm} from "./state_data";
import * as user_groups from "./user_groups";
import {user_settings} from "./user_settings";

let user_join_date: Date;
export function initialize(current_user_join_date: Date): void {
    // We keep the `user_join_date` as the present day's date if the user is a spectator
    user_join_date = current_user_join_date;
}

/*
    This is a close cousin of settings_config,
    but this has a bit more logic, and we
    ensure 100% line coverage on it.

    Our main goal with this code is to isolate
    some key modules from having to know
    about page_params and settings_config details.
*/

export function user_can_change_name(): boolean {
    if (current_user.is_admin) {
        return true;
    }
    if (realm.realm_name_changes_disabled || realm.server_name_changes_disabled) {
        return false;
    }
    return true;
}

export function user_can_change_avatar(): boolean {
    if (current_user.is_admin) {
        return true;
    }
    if (realm.realm_avatar_changes_disabled || realm.server_avatar_changes_disabled) {
        return false;
    }
    return true;
}

export function user_can_change_email(): boolean {
    if (current_user.is_admin) {
        return true;
    }
    if (realm.realm_email_changes_disabled) {
        return false;
    }
    return true;
}

export function user_can_change_logo(): boolean {
    return current_user.is_admin && realm.zulip_plan_is_not_limited;
}

function user_has_permission(policy_value: number): boolean {
    /* At present, nobody is not present in common_policy_values,
     * but we include a check for it here, so that code using
     * email_invite_to_realm_policy_values or other supersets can
     * use this function. */
    if (policy_value === settings_config.email_invite_to_realm_policy_values.nobody.code) {
        return false;
    }

    if (current_user.is_admin) {
        return true;
    }

    if (page_params.is_spectator) {
        return false;
    }

    /* At present, by_everyone is not present in common_policy_values,
     * but we include a check for it here, so that code using
     * common_message_policy_values or other supersets can use this function. */
    if (policy_value === settings_config.common_message_policy_values.by_everyone.code) {
        return true;
    }

    if (current_user.is_guest) {
        return false;
    }

    if (policy_value === settings_config.common_policy_values.by_admins_only.code) {
        return false;
    }

    if (current_user.is_moderator) {
        return true;
    }

    if (policy_value === settings_config.common_policy_values.by_moderators_only.code) {
        return false;
    }

    if (policy_value === settings_config.common_policy_values.by_members.code) {
        return true;
    }

    const current_datetime = new Date();
    const person_date_joined = new Date(user_join_date);
    const user_join_days =
        (current_datetime.getTime() - person_date_joined.getTime()) / 1000 / 86400;
    return user_join_days >= realm.realm_waiting_period_threshold;
}

export function user_can_invite_users_by_email(): boolean {
    return user_has_permission(realm.realm_invite_to_realm_policy);
}

export function user_can_create_multiuse_invite(): boolean {
    if (page_params.is_spectator) {
        return false;
    }
    return user_groups.is_user_in_group(
        realm.realm_create_multiuse_invite_group,
        current_user.user_id,
    );
}

export function user_can_subscribe_other_users(): boolean {
    return user_has_permission(realm.realm_invite_to_stream_policy);
}

export function user_can_create_private_streams(): boolean {
    if (page_params.is_spectator) {
        return false;
    }
    return user_groups.is_user_in_group(
        realm.realm_can_create_private_channel_group,
        current_user.user_id,
    );
}

export function user_can_create_public_streams(): boolean {
    if (page_params.is_spectator) {
        return false;
    }
    return user_groups.is_user_in_group(
        realm.realm_can_create_public_channel_group,
        current_user.user_id,
    );
}

export function user_can_create_web_public_streams(): boolean {
    if (!realm.server_web_public_streams_enabled || !realm.realm_enable_spectator_access) {
        return false;
    }

    if (page_params.is_spectator) {
        return false;
    }

    return user_groups.is_user_in_group(
        realm.realm_can_create_web_public_channel_group,
        current_user.user_id,
    );
}

export function user_can_move_messages_between_streams(): boolean {
    return user_has_permission(realm.realm_move_messages_between_streams_policy);
}

export function user_can_edit_all_user_groups(): boolean {
    return user_has_permission(realm.realm_user_group_edit_policy);
}

export function can_edit_user_group(group_id: number): boolean {
    if (page_params.is_spectator) {
        return false;
    }

    let can_edit_all_user_groups = user_can_edit_all_user_groups();

    if (
        !current_user.is_admin &&
        !current_user.is_moderator &&
        !user_groups.is_direct_member_of(current_user.user_id, group_id)
    ) {
        can_edit_all_user_groups = false;
    }

    if (can_edit_all_user_groups) {
        return true;
    }

    const group = user_groups.get_user_group_from_id(group_id);
    return user_groups.is_user_in_group(group.can_manage_group, current_user.user_id);
}

export function user_can_create_user_groups(): boolean {
    return user_has_permission(realm.realm_user_group_edit_policy);
}

export function user_can_add_custom_emoji(): boolean {
    return user_has_permission(realm.realm_add_custom_emoji_policy);
}

export function user_can_move_messages_to_another_topic(): boolean {
    return user_has_permission(realm.realm_edit_topic_policy);
}

export function user_can_delete_any_message(): boolean {
    if (page_params.is_spectator) {
        return false;
    }
    return user_groups.is_user_in_group(
        realm.realm_can_delete_any_message_group,
        current_user.user_id,
    );
}

export function user_can_delete_own_message(): boolean {
    return user_has_permission(realm.realm_delete_own_message_policy);
}

export function should_mask_unread_count(sub_muted: boolean): boolean {
    if (
        user_settings.web_stream_unreads_count_display_policy ===
        settings_config.web_stream_unreads_count_display_policy_values.no_streams.code
    ) {
        return true;
    }

    if (
        user_settings.web_stream_unreads_count_display_policy ===
        settings_config.web_stream_unreads_count_display_policy_values.unmuted_streams.code
    ) {
        return sub_muted;
    }

    return false;
}

export function using_dark_theme(): boolean {
    if (user_settings.color_scheme === settings_config.color_scheme_values.dark.code) {
        return true;
    }

    if (
        user_settings.color_scheme === settings_config.color_scheme_values.automatic.code &&
        window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches
    ) {
        return true;
    }
    return false;
}

export function user_email_not_configured(): boolean {
    // The following should also be true in the only circumstance
    // under which we expect this condition to be possible:
    // realm.demo_organization_scheduled_deletion_date
    return current_user.is_owner && current_user.delivery_email === "";
}

export function bot_type_id_to_string(type_id: number): string | undefined {
    const bot_type = page_params.bot_types.find((bot_type) => bot_type.type_id === type_id);

    if (bot_type === undefined) {
        return undefined;
    }

    return bot_type.name;
}

export function user_can_access_all_other_users(): boolean {
    if (page_params.is_spectator) {
        return true;
    }

    return user_groups.is_user_in_group(
        realm.realm_can_access_all_users_group,
        current_user.user_id,
    );
}

/* istanbul ignore next */
export function get_request_data_for_stream_privacy(selected_val: string): {
    is_private: boolean;
    history_public_to_subscribers: boolean;
    is_web_public: boolean;
} {
    switch (selected_val) {
        case settings_config.stream_privacy_policy_values.public.code: {
            return {
                is_private: false,
                history_public_to_subscribers: true,
                is_web_public: false,
            };
        }
        case settings_config.stream_privacy_policy_values.private.code: {
            return {
                is_private: true,
                history_public_to_subscribers: false,
                is_web_public: false,
            };
        }
        case settings_config.stream_privacy_policy_values.web_public.code: {
            return {
                is_private: false,
                history_public_to_subscribers: true,
                is_web_public: true,
            };
        }
        default: {
            return {
                is_private: true,
                history_public_to_subscribers: true,
                is_web_public: false,
            };
        }
    }
}
