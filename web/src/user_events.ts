// This module is kind of small, but it will help us keep
// server_events.js simple while breaking some circular
// dependencies that existed when this code was in people.js.
// (We should do bot updates here too.)
import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

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

export const user_update_schema = z.intersection(
    z.object({user_id: z.number()}),
    z.union([
        z.object({
            avatar_source: z.string(),
            avatar_url: z.nullable(z.string()),
            avatar_url_medium: z.nullable(z.string()),
            avatar_version: z.number(),
        }),
        z.object({bot_owner_id: z.number()}),
        z.object({
            custom_profile_field: z.object({
                id: z.number(),
                value: z.nullable(z.string()),
                rendered_value: z.optional(z.string()),
            }),
        }),
        z.object({delivery_email: z.nullable(z.string())}),
        z.object({new_email: z.string()}),
        z.object({full_name: z.string()}),
        z.object({role: z.number()}),
        z.object({email: z.string(), timezone: z.string()}),
        z.object({is_active: z.boolean()}),
    ]),
);

type UserUpdate = z.output<typeof user_update_schema>;

export const update_person = function update(event: UserUpdate): void {
    const user = people.maybe_get_user_by_id(event.user_id);

    if (!user) {
        blueslip.error("Got update_person event for unexpected user", {user_id: event.user_id});
        return;
    }

    if ("new_email" in event) {
        const user_id = event.user_id;
        const new_email = event.new_email;

        people.update_email(user_id, new_email);
        narrow_state.update_email(user_id, new_email);
        compose_state.update_email(user_id, new_email);

        if (people.is_my_user_id(event.user_id)) {
            current_user.email = new_email;
        }
    }

    if ("delivery_email" in event) {
        const delivery_email = event.delivery_email;
        user.delivery_email = delivery_email;
        user_profile.update_profile_modal_ui(user, event);
        if (people.is_my_user_id(event.user_id)) {
            assert(delivery_email !== null);
            settings_account.update_email(delivery_email);
            current_user.delivery_email = delivery_email;
            settings_account.hide_confirm_email_banner();
        }
    }

    if ("full_name" in event) {
        people.set_full_name(user, event.full_name);

        settings_users.update_user_data(event.user_id, event);
        activity_ui.redraw();
        message_live_update.update_user_full_name(event.user_id, event.full_name);
        pm_list.update_private_messages();
        user_profile.update_profile_modal_ui(user, event);
        if (people.is_my_user_id(event.user_id)) {
            current_user.full_name = event.full_name;
            settings_account.update_full_name(event.full_name);
        }
    }

    if ("role" in event) {
        user.role = event.role;
        user.is_owner = event.role === settings_config.user_role_values.owner.code;
        user.is_admin = event.role === settings_config.user_role_values.admin.code || user.is_owner;
        user.is_guest = event.role === settings_config.user_role_values.guest.code;
        user.is_moderator =
            user.is_admin || event.role === settings_config.user_role_values.moderator.code;
        settings_users.update_user_data(event.user_id, event);
        user_profile.update_profile_modal_ui(user, event);

        if (people.is_my_user_id(event.user_id) && current_user.is_owner !== user.is_owner) {
            current_user.is_owner = user.is_owner;
            settings_org.maybe_disable_widgets();
            settings_org.enable_or_disable_group_permission_settings();
            settings.update_lock_icon_in_sidebar();
        }

        if (people.is_my_user_id(event.user_id) && current_user.is_admin !== user.is_admin) {
            current_user.is_admin = user.is_admin;
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
            people.is_my_user_id(event.user_id) &&
            current_user.is_moderator !== user.is_moderator
        ) {
            current_user.is_moderator = user.is_moderator;
        }
    }

    if ("avatar_url" in event) {
        const url = event.avatar_url;
        user.avatar_url = url;
        user.avatar_version = event.avatar_version;

        if (people.is_my_user_id(event.user_id)) {
            current_user.avatar_source = event.avatar_source;
            current_user.avatar_url = url;
            current_user.avatar_url_medium = event.avatar_url_medium;
            $("#user-avatar-upload-widget .image-block").attr("src", event.avatar_url_medium);
            $("#personal-menu .header-button-avatar-image").attr(
                "src",
                `${event.avatar_url_medium}`,
            );
        }

        message_live_update.update_avatar(user.user_id, event.avatar_url);
        user_profile.update_profile_modal_ui(user, event);
    }

    if ("custom_profile_field" in event) {
        people.set_custom_profile_field_data(event.user_id, event.custom_profile_field);
        user_profile.update_user_custom_profile_fields(user);
        if (event.user_id === people.my_current_user_id()) {
            navbar_alerts.maybe_toggle_empty_required_profile_fields_banner();

            const field_id = event.custom_profile_field.id;
            const field_value = people.get_custom_profile_data(event.user_id, field_id)?.value;
            const is_field_required = realm.custom_profile_fields?.find(
                (f) => field_id === f.id,
            )?.required;
            if (is_field_required) {
                const $custom_user_field = $(
                    `.profile-settings-form .custom_user_field[data-field-id="${CSS.escape(`${field_id}`)}"]`,
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

    if ("timezone" in event) {
        user.timezone = event.timezone;
    }

    if ("bot_owner_id" in event) {
        assert(user.is_bot);
        user.bot_owner_id = event.bot_owner_id;
        user_profile.update_profile_modal_ui(user, event);
    }

    if ("is_active" in event) {
        const is_bot_user = user.is_bot;
        if (event.is_active) {
            people.add_active_user(user);
            settings_users.update_view_on_reactivate(event.user_id, is_bot_user);
        } else {
            people.deactivate(user);
            stream_events.remove_deactivated_user_from_all_streams(event.user_id);
            user_group_edit.remove_deactivated_user_from_all_groups(event.user_id);
            settings_users.update_view_on_deactivate(event.user_id, is_bot_user);
        }
        buddy_list.insert_or_move([event.user_id]);
        settings_account.maybe_update_deactivate_account_button();
        if (is_bot_user) {
            settings_users.update_bot_data(event.user_id);
        } else if (!event.is_active) {
            // A human user deactivated, update 'Export permissions' table.
            settings_exports.remove_export_consent_data_and_redraw(event.user_id);
        }
    }
};
