var user_events = (function () {

var exports = {};

// This module is kind of small, but it will help us keep
// server_events.js simple while breaking some circular
// dependencies that existed when this code was in people.js.
// (We should do bot updates here too.)

exports.update_person = function update(person) {
    var person_obj = people.get_person_from_user_id(person.user_id);

    if (!person_obj) {
        blueslip.error("Got update_person event for unexpected user " + person.user_id);
        return;
    }

    if (_.has(person, 'new_email')) {
        var user_id = person.user_id;
        var new_email = person.new_email;

        narrow_state.update_email(user_id, new_email);
        compose.update_email(user_id, new_email);

        if (people.is_my_user_id(person.user_id)) {
            settings_account.update_email(new_email);
        }

        people.update_email(user_id, new_email);
    }

    if (_.has(person, 'full_name')) {
        people.set_full_name(person_obj, person.full_name);

        settings_users.update_user_data(person.user_id, person);
        activity.redraw();
        message_live_update.update_user_full_name(person.user_id, person.full_name);
        pm_list.update_private_messages();
        if (people.is_my_user_id(person.user_id)) {
            settings_account.update_full_name(person.full_name);
        }
    }

    if (_.has(person, 'is_admin')) {
        person_obj.is_admin = person.is_admin;

        if (people.is_my_user_id(person.user_id)) {
            page_params.is_admin = person.is_admin;
            admin.show_or_hide_menu_item();
        }
    }

    if (_.has(person, 'avatar_url')) {
        var url = person.avatar_url;
        person_obj.avatar_url = url;

        if (people.is_my_user_id(person.user_id)) {
            page_params.avatar_source = person.avatar_source;
            page_params.avatar_url = url;
            page_params.avatar_url_medium = person.avatar_url_medium;
            $("#user-avatar-block").attr("src", person.avatar_url_medium);
        }

        message_live_update.update_avatar(person_obj.user_id, person.avatar_url);
    }

    if (_.has(person, 'custom_profile_field')) {
        people.set_custom_profile_field_data(person.user_id, person.custom_profile_field);
    }

     if (_.has(person, 'timezone')) {
         person_obj.timezone = person.timezone;
    }
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = user_events;
}
