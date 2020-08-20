"use strict";

// This module is kind of small, but it will help us keep
// server_events.js simple while breaking some circular
// dependencies that existed when this code was in people.js.
// (We should do bot updates here too.)
const people = require("./people");
const settings_config = require("./settings_config");

exports.update_person = function update(person) {
    const person_obj = people.get_by_user_id(person.user_id);

    if (!person_obj) {
        blueslip.error("Got update_person event for unexpected user " + person.user_id);
        return;
    }

    if (Object.prototype.hasOwnProperty.call(person, "new_email")) {
        const user_id = person.user_id;
        const new_email = person.new_email;

        narrow_state.update_email(user_id, new_email);
        compose.update_email(user_id, new_email);

        if (people.is_my_user_id(person.user_id)) {
            page_params.email = new_email;
        }

        people.update_email(user_id, new_email);
    }

    if (Object.prototype.hasOwnProperty.call(person, "delivery_email")) {
        const delivery_email = person.delivery_email;

        if (people.is_my_user_id(person.user_id)) {
            settings_account.update_email(delivery_email);
            page_params.delivery_email = delivery_email;
        }
    }

    if (Object.prototype.hasOwnProperty.call(person, "full_name")) {
        people.set_full_name(person_obj, person.full_name);

        settings_users.update_user_data(person.user_id, person);
        activity.redraw();
        message_live_update.update_user_full_name(person.user_id, person.full_name);
        pm_list.update_private_messages();
        if (people.is_my_user_id(person.user_id)) {
            page_params.full_name = person.full_name;
            settings_account.update_full_name(person.full_name);
        }
    }

    if (Object.prototype.hasOwnProperty.call(person, "role")) {
        person_obj.is_owner = person.role === settings_config.user_role_values.owner.code;
        person_obj.is_admin =
            person.role === settings_config.user_role_values.admin.code || person_obj.is_owner;
        person_obj.is_guest = person.role === settings_config.user_role_values.guest.code;
        settings_users.update_user_data(person.user_id, person);

        if (people.is_my_user_id(person.user_id) && page_params.is_owner !== person_obj.is_owner) {
            page_params.is_owner = person_obj.is_owner;
            settings_org.maybe_disable_widgets();
        }

        if (people.is_my_user_id(person.user_id) && page_params.is_admin !== person_obj.is_admin) {
            page_params.is_admin = person_obj.is_admin;
            gear_menu.update_org_settings_menu_item();
            settings_linkifiers.maybe_disable_widgets();
            settings_org.maybe_disable_widgets();
            settings_profile_fields.maybe_disable_widgets();
            settings_streams.maybe_disable_widgets();
        }
    }

    if (Object.prototype.hasOwnProperty.call(person, "avatar_url")) {
        const url = person.avatar_url;
        person_obj.avatar_url = url;
        person_obj.avatar_version = person.avatar_version;

        if (people.is_my_user_id(person.user_id)) {
            page_params.avatar_source = person.avatar_source;
            page_params.avatar_url = url;
            page_params.avatar_url_medium = person.avatar_url_medium;
            $("#user-avatar-upload-widget .image-block").attr("src", person.avatar_url_medium);
        }

        message_live_update.update_avatar(person_obj.user_id, person.avatar_url);
    }

    if (Object.prototype.hasOwnProperty.call(person, "custom_profile_field")) {
        people.set_custom_profile_field_data(person.user_id, person.custom_profile_field);
    }

    if (Object.prototype.hasOwnProperty.call(person, "timezone")) {
        person_obj.timezone = person.timezone;
    }

    if (Object.prototype.hasOwnProperty.call(person, "bot_owner_id")) {
        person_obj.bot_owner_id = person.bot_owner_id;
    }
};

window.user_events = exports;
