// This module is kind of small, but it will help us keep
// server_events.js simple while breaking some circular
// dependencies that existed when this code was in people.js.
// (We should do bot updates here too.)
import $ from "jquery";

import * as activity_ui from "./activity_ui.ts";
import * as blueslip from "./blueslip.ts";
import {buddy_list} from "./buddy_list.ts";
import * as compose_state from "./compose_state.ts";
import * as message_live_update from "./message_live_update.ts";
import * as narrow_state from "./narrow_state.ts";
import * as navbar_alerts from "./navbar_alerts.ts";
import * as people from "./people.ts";
import * as pm_list from "./pm_list.ts";
import * as settings from "./settings.ts";
import * as settings_account from "./settings_account.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_exports from "./settings_exports.ts";
import * as settings_linkifiers from "./settings_linkifiers.ts";
import * as settings_org from "./settings_org.ts";
import * as settings_profile_fields from "./settings_profile_fields.ts";
import * as settings_realm_user_settings_defaults from "./settings_realm_user_settings_defaults.ts";
import * as settings_streams from "./settings_streams.ts";
import * as settings_users from "./settings_users.ts";
import {current_user, realm} from "./state_data.ts";
import * as stream_events from "./stream_events.ts";
import * as user_group_edit from "./user_group_edit.ts";
import * as user_profile from "./user_profile.ts";

export const update_person = function update(person) {
    const person_obj = people.maybe_get_user_by_id(person.user_id);

    if (!person_obj) {
        blueslip.error("Got update_person event for unexpected user", {user_id: person.user_id});
        return;
    }

    if (Object.hasOwn(person, "new_email")) {
        const user_id = person.user_id;
        const new_email = person.new_email;

        people.update_email(user_id, new_email);
        narrow_state.update_email(user_id, new_email);
        compose_state.update_email(user_id, new_email);

        if (people.is_my_user_id(person.user_id)) {
            current_user.email = new_email;
        }
    }

    if (Object.hasOwn(person, "delivery_email")) {
        const delivery_email = person.delivery_email;
        person_obj.delivery_email = delivery_email;
        user_profile.update_profile_modal_ui(person_obj, person);
        if (people.is_my_user_id(person.user_id)) {
            settings_account.update_email(delivery_email);
            current_user.delivery_email = delivery_email;
            settings_account.hide_confirm_email_banner();
        }
    }

    if (Object.hasOwn(person, "full_name")) {
        people.set_full_name(person_obj, person.full_name);

        settings_users.update_user_data(person.user_id, person);
        activity_ui.redraw();
        message_live_update.update_user_full_name(person.user_id, person.full_name);
        pm_list.update_private_messages();
        user_profile.update_profile_modal_ui(person_obj, person);
        if (people.is_my_user_id(person.user_id)) {
            current_user.full_name = person.full_name;
            settings_account.update_full_name(person.full_name);
        }
    }

    if (Object.hasOwn(person, "role")) {
        person_obj.role = person.role;
        person_obj.is_owner = person.role === settings_config.user_role_values.owner.code;
        person_obj.is_admin =
            person.role === settings_config.user_role_values.admin.code || person_obj.is_owner;
        person_obj.is_guest = person.role === settings_config.user_role_values.guest.code;
        person_obj.is_moderator = person.role === settings_config.user_role_values.moderator.code;
        settings_users.update_user_data(person.user_id, person);
        user_profile.update_profile_modal_ui(person_obj, person);

        if (people.is_my_user_id(person.user_id) && current_user.is_owner !== person_obj.is_owner) {
            current_user.is_owner = person_obj.is_owner;
            settings_org.maybe_disable_widgets();
            settings_org.enable_or_disable_group_permission_settings();
            settings.update_lock_icon_in_sidebar();
        }

        if (people.is_my_user_id(person.user_id) && current_user.is_admin !== person_obj.is_admin) {
            current_user.is_admin = person_obj.is_admin;
            settings_linkifiers.maybe_disable_widgets();
            settings_org.maybe_disable_widgets();
            settings_org.enable_or_disable_group_permission_settings();
            settings_profile_fields.maybe_disable_widgets();
            settings_streams.maybe_disable_widgets();
            settings_realm_user_settings_defaults.maybe_disable_widgets();
            settings_account.update_account_settings_display();
            settings.update_lock_icon_in_sidebar();
        }

        if (
            people.is_my_user_id(person.user_id) &&
            current_user.is_moderator !== person_obj.is_moderator
        ) {
            current_user.is_moderator = person_obj.is_moderator;
        }
    }

    if (Object.hasOwn(person, "is_billing_admin")) {
        person_obj.is_billing_admin = person.is_billing_admin;
        if (people.is_my_user_id(person.user_id)) {
            current_user.is_billing_admin = person_obj.is_billing_admin;
        }
    }

    if (Object.hasOwn(person, "avatar_url")) {
        const url = person.avatar_url;
        person_obj.avatar_url = url;
        person_obj.avatar_version = person.avatar_version;

        if (people.is_my_user_id(person.user_id)) {
            current_user.avatar_source = person.avatar_source;
            current_user.avatar_url = url;
            current_user.avatar_url_medium = person.avatar_url_medium;
            $("#user-avatar-upload-widget .image-block").attr("src", person.avatar_url_medium);
            $("#personal-menu .header-button-avatar").attr("src", `${person.avatar_url_medium}`);
        }

        message_live_update.update_avatar(person_obj.user_id, person.avatar_url);
        user_profile.update_profile_modal_ui(person_obj, person);
    }

    if (Object.hasOwn(person, "custom_profile_field")) {
        people.set_custom_profile_field_data(person.user_id, person.custom_profile_field);
        user_profile.update_user_custom_profile_fields(person_obj);
        if (person.user_id === people.my_current_user_id()) {
            navbar_alerts.maybe_show_empty_required_profile_fields_alert();

            const field_id = person.custom_profile_field.id;
            const field_value = people.get_custom_profile_data(person.user_id, field_id)?.value;
            const is_field_required = realm.custom_profile_fields?.find(
                (f) => field_id === f.id,
            )?.required;
            if (is_field_required) {
                const $custom_user_field = $(
                    `.profile-settings-form .custom_user_field[data-field-id="${CSS.escape(field_id)}"]`,
                );
                const $field = $custom_user_field.find(".settings-profile-user-field");
                const $required_symbol = $custom_user_field.find(".required-symbol");
                if (!field_value) {
                    if (!$field.hasClass("empty-required-field")) {
                        $field.addClass("empty-required-field");
                        $required_symbol.removeClass("hidden");
                    }
                } else {
                    if ($field.hasClass("empty-required-field")) {
                        $field.removeClass("empty-required-field");
                        $required_symbol.addClass("hidden");
                    }
                }
            }
        }
    }

    if (Object.hasOwn(person, "timezone")) {
        person_obj.timezone = person.timezone;
    }

    if (Object.hasOwn(person, "bot_owner_id")) {
        person_obj.bot_owner_id = person.bot_owner_id;
        user_profile.update_profile_modal_ui(person_obj, person);
    }

    if (Object.hasOwn(person, "is_active")) {
        if (person.is_active) {
            people.add_active_user(person_obj);
            settings_users.update_view_on_reactivate(person.user_id);
        } else {
            people.deactivate(person_obj);
            stream_events.remove_deactivated_user_from_all_streams(person.user_id);
            user_group_edit.remove_deactivated_user_from_all_groups(person.user_id);
            settings_users.update_view_on_deactivate(person.user_id);
            buddy_list.maybe_remove_user_id({user_id: person.user_id});
        }
        settings_account.maybe_update_deactivate_account_button();
        if (people.is_valid_bot_user(person.user_id)) {
            settings_users.update_bot_data(person.user_id);
        } else if (!person.is_active) {
            // A human user deactivated, update 'Export permissions' table.
            settings_exports.remove_export_consent_data_and_redraw(person.user_id);
        }
    }
};
