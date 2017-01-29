var user_events = (function () {

var exports = {};

// This module is kind of small, but it will help us keep
// server_events.js simple while breaking some circular
// dependencies that existed when this code was in people.js.
// (We should do bot updates here too.)

exports.update_person = function update(person) {
    var person_obj = people.get_person_from_user_id(person.user_id);

    if (!person_obj) {
        blueslip.error("Got update_person event for unexpected user",
                       {email: person.user_id});
        return;
    }

    if (_.has(person, 'full_name')) {
        people.set_full_name(person_obj, person.full_name);

        admin.update_user_full_name(person.email, person.full_name);
        activity.redraw();
        message_live_update.update_user_full_name(person.user_id, person.full_name);
        pm_list.update_private_messages();
    }

    if (_.has(person, 'is_admin')) {
        person_obj.is_admin = person.is_admin;

        if (people.is_my_user_id(person.user_id)) {
            page_params.is_admin = person.is_admin;
            admin.show_or_hide_menu_item();
        }
    }

    if (_.has(person, 'avatar_url')) {
        var url = person.avatar_url + "&y=" + new Date().getTime();
        person_obj.avatar_url = url;

        if (people.is_my_user_id(person.user_id)) {
          page_params.avatar_url = url;
          $("#user-settings-avatar").attr("src", url);
        }

        message_live_update.update_avatar(person_obj);
    }
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = user_events;
}
