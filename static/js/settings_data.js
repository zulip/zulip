import * as settings_config from "./settings_config";

/*
    This is a close cousin of settings_config,
    but this has a bit more logic, and we
    ensure 100% line coverage on it.

    Our main goal with this code is to isolate
    some key modules from having to know
    about page_params and settings_config details.
*/

export function show_email() {
    if (
        page_params.realm_email_address_visibility ===
        settings_config.email_address_visibility_values.everyone.code
    ) {
        return true;
    }
    if (
        page_params.realm_email_address_visibility ===
        settings_config.email_address_visibility_values.admins_only.code
    ) {
        return page_params.is_admin;
    }
    return undefined;
}

export function email_for_user_settings(person) {
    if (!show_email()) {
        return undefined;
    }

    if (
        page_params.is_admin &&
        person.delivery_email &&
        page_params.realm_email_address_visibility ===
            settings_config.email_address_visibility_values.admins_only.code
    ) {
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

export function user_can_change_logo() {
    return page_params.is_admin && page_params.zulip_plan_is_not_limited;
}
