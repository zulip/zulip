/*
    This is a close cousin of settings_config,
    but this has a bit more logic, and we
    ensure 100% line coverage on it.

    Our main goal with this code is to isolate
    some key modules from having to know
    about page_params.
*/

exports.email_for_user_settings = function (person) {
    if (!settings_org.show_email()) {
        return;
    }

    if (page_params.is_admin && person.delivery_email) {
        return person.delivery_email;
    }

    return person.email;
};

exports.get_time_preferences = function (user_timezone) {
    if (page_params.twenty_four_hour_time) {
        return {
            timezone: user_timezone,
            format: "H:mm",
        };
    }
    return {
        timezone: user_timezone,
        format: "h:mm A",
    };
};
