import {page_params} from "./page_params";
import * as settings_config from "./settings_config";
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

function user_can_access_delivery_email(): boolean {
    // This function checks whether the current user should expect to
    // see .delivery_email fields on user objects that it can access.
    //
    // If false, either everyone has access to emails (and there is no
    // delivery_email field for anyone) or this user does not have
    // access to emails (and this client will never receive a user
    // object with a delivery_email field).
    if (
        page_params.realm_email_address_visibility ===
        settings_config.email_address_visibility_values.admins_only.code
    ) {
        return page_params.is_admin;
    }

    if (
        page_params.realm_email_address_visibility ===
        settings_config.email_address_visibility_values.moderators.code
    ) {
        return page_params.is_admin || page_params.is_moderator;
    }

    return false;
}

export function show_email(): boolean {
    if (
        page_params.realm_email_address_visibility ===
        settings_config.email_address_visibility_values.everyone.code
    ) {
        return true;
    }
    return user_can_access_delivery_email();
}

// TODO: Move this to people when converting it
// to TypeScript.
interface Person {
    delivery_email: string;
    email: string;
}

export function email_for_user_settings(person: Person): string | undefined {
    if (!show_email()) {
        return undefined;
    }

    if (person.delivery_email && user_can_access_delivery_email()) {
        return person.delivery_email;
    }

    return person.email;
}

export function get_time_preferences(user_timezone: string): {
    timezone: string;
    format: string;
} {
    if (user_settings.twenty_four_hour_time) {
        return {
            timezone: user_timezone,
            format: "H:mm",
        };
    }
    return {
        timezone: user_timezone,
        format: "h:mm a",
    };
}

export function user_can_change_name(): boolean {
    if (page_params.is_admin) {
        return true;
    }
    if (page_params.realm_name_changes_disabled || page_params.server_name_changes_disabled) {
        return false;
    }
    return true;
}

export function user_can_change_avatar(): boolean {
    if (page_params.is_admin) {
        return true;
    }
    if (page_params.realm_avatar_changes_disabled || page_params.server_avatar_changes_disabled) {
        return false;
    }
    return true;
}

export function user_can_change_logo(): boolean {
    return page_params.is_admin && page_params.zulip_plan_is_not_limited;
}

function user_has_permission(policy_value: number): boolean {
    /* At present, nobody and by_owners_only is not present in
     * common_policy_values, but we include a check for it here,
     * so that code using create_web_public_stream_policy_values
     * or other supersets can use this function. */
    if (policy_value === settings_config.create_web_public_stream_policy_values.nobody.code) {
        return false;
    }

    if (page_params.is_owner) {
        return true;
    }

    if (
        policy_value === settings_config.create_web_public_stream_policy_values.by_owners_only.code
    ) {
        return false;
    }

    if (page_params.is_admin) {
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

    if (page_params.is_guest) {
        return false;
    }

    if (policy_value === settings_config.common_policy_values.by_admins_only.code) {
        return false;
    }

    if (page_params.is_moderator) {
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
    return user_join_days >= page_params.realm_waiting_period_threshold;
}

export function user_can_invite_others_to_realm(): boolean {
    if (
        page_params.realm_invite_to_realm_policy ===
        settings_config.invite_to_realm_policy_values.nobody.code
    ) {
        return false;
    }
    return user_has_permission(page_params.realm_invite_to_realm_policy);
}

export function user_can_subscribe_other_users(): boolean {
    return user_has_permission(page_params.realm_invite_to_stream_policy);
}

export function user_can_unsubscribe_other_users(): boolean {
    return page_params.is_admin;
}

export function user_can_create_private_streams(): boolean {
    return user_has_permission(page_params.realm_create_private_stream_policy);
}

export function user_can_create_public_streams(): boolean {
    return user_has_permission(page_params.realm_create_public_stream_policy);
}

export function user_can_create_web_public_streams(): boolean {
    if (
        !page_params.server_web_public_streams_enabled ||
        !page_params.realm_enable_spectator_access
    ) {
        return false;
    }

    return user_has_permission(page_params.realm_create_web_public_stream_policy);
}

export function user_can_move_messages_between_streams(): boolean {
    return user_has_permission(page_params.realm_move_messages_between_streams_policy);
}

export function user_can_edit_user_groups(): boolean {
    return user_has_permission(page_params.realm_user_group_edit_policy);
}

export function user_can_add_custom_emoji(): boolean {
    return user_has_permission(page_params.realm_add_custom_emoji_policy);
}

export function user_can_move_messages_to_another_topic(): boolean {
    return user_has_permission(page_params.realm_edit_topic_policy);
}

export function user_can_delete_own_message(): boolean {
    return user_has_permission(page_params.realm_delete_own_message_policy);
}

export function using_dark_theme(): boolean {
    if (user_settings.color_scheme === settings_config.color_scheme_values.night.code) {
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
