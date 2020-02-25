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
