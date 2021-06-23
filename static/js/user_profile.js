import {parseISO} from "date-fns";
import $ from "jquery";

import render_user_group_list_item from "../templates/user_group_list_item.hbs";
import render_user_profile_modal from "../templates/user_profile_modal.hbs";
import render_user_stream_list_item from "../templates/user_stream_list_item.hbs";

import * as buddy_data from "./buddy_data";
import * as components from "./components";
import * as hash_util from "./hash_util";
import {$t} from "./i18n";
import * as ListWidget from "./list_widget";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as people from "./people";
import * as popovers from "./popovers";
import * as settings_account from "./settings_account";
import * as settings_data from "./settings_data";
import * as settings_profile_fields from "./settings_profile_fields";
import * as stream_data from "./stream_data";
import * as user_groups from "./user_groups";
import * as util from "./util";

function compare_by_name(a, b) {
    return util.strcmp(a.name, b.name);
}

function format_user_stream_list_item(stream) {
    return render_user_stream_list_item({
        name: stream.name,
        stream_id: stream.stream_id,
        stream_color: stream.color,
        invite_only: stream.invite_only,
        is_web_public: stream.is_web_public,
        stream_edit_url: hash_util.stream_edit_uri(stream),
    });
}

function format_user_group_list_item(group) {
    return render_user_group_list_item({
        group_id: group.id,
        name: group.name,
    });
}

function render_user_stream_list(streams, user) {
    streams.sort(compare_by_name);
    const container = $("#user-profile-modal .user-stream-list");
    container.empty();
    ListWidget.create(container, streams, {
        name: `user-${user.user_id}-stream-list`,
        modifier(item) {
            return format_user_stream_list_item(item);
        },
        simplebar_container: $("#user-profile-modal .modal-body"),
    });
}

function render_user_group_list(groups, user) {
    groups.sort(compare_by_name);
    const container = $("#user-profile-modal .user-group-list");
    container.empty();
    ListWidget.create(container, groups, {
        name: `user-${user.user_id}-group-list`,
        modifier(item) {
            return format_user_group_list_item(item);
        },
        simplebar_container: $("#user-profile-modal .modal-body"),
    });
}

function get_custom_profile_field_data(user, field, field_types, dateFormat) {
    const field_value = people.get_custom_profile_data(user.user_id, field.id);
    const field_type = field.type;
    const profile_field = {};

    if (!field_value) {
        return profile_field;
    }
    if (!field_value.value) {
        return profile_field;
    }
    profile_field.name = field.name;
    profile_field.is_user_field = false;
    profile_field.is_link = field_type === field_types.URL.id;
    profile_field.is_external_account = field_type === field_types.EXTERNAL_ACCOUNT.id;
    profile_field.type = field_type;

    switch (field_type) {
        case field_types.DATE.id:
            profile_field.value = dateFormat.format(parseISO(field_value.value));
            break;
        case field_types.USER.id:
            profile_field.id = field.id;
            profile_field.is_user_field = true;
            profile_field.value = field_value.value;
            break;
        case field_types.SELECT.id: {
            const field_choice_dict = JSON.parse(field.field_data);
            profile_field.value = field_choice_dict[field_value.value].text;
            break;
        }
        case field_types.SHORT_TEXT.id:
        case field_types.LONG_TEXT.id:
            profile_field.value = field_value.value;
            profile_field.rendered_value = field_value.rendered_value;
            break;
        case field_types.EXTERNAL_ACCOUNT.id:
            profile_field.value = field_value.value;
            profile_field.field_data = JSON.parse(field.field_data);
            profile_field.link = settings_profile_fields.get_external_account_link(profile_field);
            break;
        default:
            profile_field.value = field_value.value;
    }
    return profile_field;
}

export function hide_user_profile() {
    overlays.close_modal("#user-profile-modal");
}

export function show_user_profile(user) {
    popovers.hide_all();

    const dateFormat = new Intl.DateTimeFormat("default", {dateStyle: "long"});
    const field_types = page_params.custom_profile_field_types;
    const profile_data = page_params.custom_profile_fields
        .map((f) => get_custom_profile_field_data(user, f, field_types, dateFormat))
        .filter((f) => f.name !== undefined);
    const user_streams = stream_data.get_subscribed_streams_for_user(user.user_id);
    const groups_of_user = user_groups.get_user_groups_of_user(user.user_id);
    const args = {
        full_name: user.full_name,
        email: people.get_visible_email(user),
        profile_data,
        user_avatar: "avatar/" + user.email + "/medium",
        is_me: people.is_current_user(user.email),
        date_joined: dateFormat.format(parseISO(user.date_joined)),
        last_seen: buddy_data.user_last_seen_time_status(user.user_id),
        show_email: settings_data.show_email(),
        user_time: people.get_user_time(user.user_id),
        user_type: people.get_user_type(user.user_id),
        user_is_guest: user.is_guest,
    };

    $("#user-profile-modal-holder").html(render_user_profile_modal(args));
    $("#user-profile-modal").modal("show");
    $(".tabcontent").hide();
    $("#profile-tab").show(); // Show general profile details by default.
    const opts = {
        selected: 0,
        child_wants_focus: true,
        values: [
            {label: $t({defaultMessage: "Profile"}), key: "profile-tab"},
            {label: $t({defaultMessage: "Streams"}), key: "streams-tab"},
            {label: $t({defaultMessage: "User groups"}), key: "groups-tab"},
        ],
        callback(name, key) {
            $(".tabcontent").hide();
            $("#" + key).show();
            switch (key) {
                case "groups-tab":
                    render_user_group_list(groups_of_user, user);
                    break;
                case "streams-tab":
                    render_user_stream_list(user_streams, user);
                    break;
            }
        },
    };

    const elem = components.toggle(opts).get();
    elem.addClass("large allow-overflow");
    $("#tab-toggle").append(elem);

    settings_account.initialize_custom_user_type_fields(
        "#user-profile-modal #content",
        user.user_id,
        false,
        false,
    );
}

export function register_click_handlers() {
    $("body").on("click", ".info_popover_actions .view_full_user_profile", (e) => {
        const user_id = popovers.elem_to_user_id($(e.target).parents("ul"));
        const user = people.get_by_user_id(user_id);
        show_user_profile(user);
        e.stopPropagation();
        e.preventDefault();
    });

    /* These click handlers are implemented as just deep links to the
     * relevant part of the Zulip UI, so we don't want preventDefault,
     * but we do want to close the modal when you click them. */
    $("body").on("click", "#user-profile-modal #name #edit-button", () => {
        hide_user_profile();
    });

    $("body").on("click", "#user-profile-modal .stream_list_item", () => {
        hide_user_profile();
    });
}
