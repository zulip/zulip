import {page_params} from "./page_params";
import * as people from "./people";
import * as settings_config from "./settings_config";

/*
    This is a close cousin of settings_config,
    but this has a bit more logic, and we
    ensure 100% line coverage on it.

    Our main goal with this code is to isolate
    some key modules from having to know
    about page_params and settings_config details.
*/

function user_can_access_delivery_email() {
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

export function show_email() {
    if (
        page_params.realm_email_address_visibility ===
        settings_config.email_address_visibility_values.everyone.code
    ) {
        return true;
    }
    return user_can_access_delivery_email();
}

export function email_for_user_settings(person) {
    if (!show_email()) {
        return undefined;
    }

    if (person.delivery_email && user_can_access_delivery_email()) {
        return person.delivery_email;
    }

    return person.email;
}

export function get_time_preferences(user_timezone) {
    if (page_params.twenty_four_hour_time) {
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

export function user_can_change_name() {
    if (page_params.is_admin) {
        return true;
    }
    if (page_params.realm_name_changes_disabled || page_params.server_name_changes_disabled) {
        return false;
    }
    return true;
}

export function user_can_change_avatar() {
    if (page_params.is_admin) {
        return true;
    }
    if (page_params.realm_avatar_changes_disabled || page_params.server_avatar_changes_disabled) {
        return false;
    }
    return true;
}

export function user_can_change_logo() {
    return page_params.is_admin && page_params.zulip_plan_is_not_limited;
}

function user_has_permission(policy_value) {
    if (page_params.is_admin) {
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

    const person = people.get_by_user_id(page_params.user_id);
    const current_datetime = new Date(Date.now());
    const person_date_joined = new Date(person.date_joined);
    const days = (current_datetime - person_date_joined) / 1000 / 86400;

    return days >= page_params.realm_waiting_period_threshold;
}

export function user_can_invite_others_to_realm() {
    return user_has_permission(page_params.realm_invite_to_realm_policy);
}

export function user_can_subscribe_other_users() {
    return user_has_permission(page_params.realm_invite_to_stream_policy);
}

export function user_can_unsubscribe_other_users() {
    return page_params.is_admin;
}

export function user_can_create_streams() {
    return user_has_permission(page_params.realm_create_stream_policy);
}

export function user_can_move_messages_between_streams() {
    return user_has_permission(page_params.realm_move_messages_between_streams_policy);
}

export function user_can_edit_user_groups() {
    return user_has_permission(page_params.realm_user_group_edit_policy);
}

export function user_can_edit_topic_of_any_message() {
    if (
        page_params.realm_edit_topic_policy ===
        settings_config.common_message_policy_values.by_everyone.code
    ) {
        return true;
    }
    return user_has_permission(page_params.realm_edit_topic_policy);
}

export function using_dark_theme() {
    if (page_params.color_scheme === settings_config.color_scheme_values.night.code) {
        return true;
    }

    if (
        page_params.color_scheme === settings_config.color_scheme_values.automatic.code &&
        window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches
    ) {
        return true;
    }
    return false;
}
