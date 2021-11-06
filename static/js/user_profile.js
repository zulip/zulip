import {parseISO} from "date-fns";
import $ from "jquery";

import render_user_group_list_item from "../templates/user_group_list_item.hbs";
import render_user_profile_modal from "../templates/user_profile_modal.hbs";
import render_user_stream_list_item from "../templates/user_stream_list_item.hbs";

import * as browser_history from "./browser_history";
import * as buddy_data from "./buddy_data";
import * as channel from "./channel";
import * as components from "./components";
import * as hash_util from "./hash_util";
import {$t, $t_html} from "./i18n";
import * as ListWidget from "./list_widget";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as people from "./people";
import * as popovers from "./popovers";
import * as settings_account from "./settings_account";
import * as settings_data from "./settings_data";
import * as settings_profile_fields from "./settings_profile_fields";
import * as stream_data from "./stream_data";
import * as stream_edit from "./stream_edit";
import * as sub_store from "./sub_store";
import * as ui_report from "./ui_report";
import * as user_groups from "./user_groups";
import * as util from "./util";

function compare_by_name(a, b) {
    return util.strcmp(a.name, b.name);
}

function format_user_stream_list_item(stream, user) {
    const show_unsubscribe_button =
        people.is_my_user_id(user.user_id) || settings_data.user_can_unsubscribe_other_users();
    const show_private_stream_unsub_tooltip =
        people.is_my_user_id(user.user_id) && stream.invite_only;
    return render_user_stream_list_item({
        name: stream.name,
        stream_id: stream.stream_id,
        stream_color: stream.color,
        invite_only: stream.invite_only,
        is_web_public: stream.is_web_public,
        show_unsubscribe_button,
        show_private_stream_unsub_tooltip,
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
            return format_user_stream_list_item(item, user);
        },
        filter: {
            element: $("#user-profile-streams-tab .stream-search"),
            predicate(item, value) {
                return item && item.name.toLocaleLowerCase().includes(value);
            },
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
        user_id: user.user_id,
        full_name: user.full_name,
        email: people.get_visible_email(user),
        profile_data,
        user_avatar: "avatar/" + user.user_id + "/medium",
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
            {label: $t({defaultMessage: "Streams"}), key: "user-profile-streams-tab"},
            {label: $t({defaultMessage: "User groups"}), key: "user-profile-groups-tab"},
        ],
        callback(name, key) {
            $(".tabcontent").hide();
            $("#" + key).show();
            switch (key) {
                case "user-profile-groups-tab":
                    render_user_group_list(groups_of_user, user);
                    break;
                case "user-profile-streams-tab":
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

function handle_remove_stream_subscription(target_user_id, sub, success, failure) {
    if (people.is_my_user_id(target_user_id)) {
        // Self unsubscribe.
        channel.del({
            url: "/json/users/me/subscriptions",
            data: {subscriptions: JSON.stringify([sub.name])},
            success,
            error: failure,
        });
    } else {
        // Unsubscribed by admin.
        stream_edit.remove_user_from_stream(target_user_id, sub, success, failure);
    }
}

export function register_click_handlers() {
    $("body").on("click", ".info_popover_actions .view_full_user_profile", (e) => {
        const user_id = popovers.elem_to_user_id($(e.target).parents("ul"));
        const user = people.get_by_user_id(user_id);
        show_user_profile(user);
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", "#user-profile-modal .remove-subscription-button", (e) => {
        e.preventDefault();
        const stream_row = $(e.currentTarget).closest("[data-stream-id]");
        const stream_id = Number.parseInt(stream_row.attr("data-stream-id"), 10);
        const sub = sub_store.get(stream_id);
        const target_user_id = Number.parseInt(
            stream_row.closest("#user-profile-modal").attr("data-user-id"),
            10,
        );
        const alert_box = $("#user-profile-streams-tab .stream_list_info");

        function removal_success(data) {
            if (data.removed.length > 0) {
                // Most of the work for handling the unsubscribe is done
                // by the subscription -> remove event we will get.
                // However, the user profile component has not yet
                // implemented live update, so we do update its
                // UI manually here by removing the stream from this list.
                stream_row.remove();

                ui_report.success(
                    $t_html({defaultMessage: "Unsubscribed successfully!"}),
                    alert_box,
                    1200,
                );
            } else {
                ui_report.client_error(
                    $t_html({defaultMessage: "Already not subscribed."}),
                    alert_box,
                    1200,
                );
            }
        }

        function removal_failure() {
            let error_message;
            if (people.is_my_user_id(target_user_id)) {
                error_message = $t(
                    {defaultMessage: "Error in unsubscribing from #{stream_name}"},
                    {stream_name: sub.name},
                );
            } else {
                error_message = $t(
                    {defaultMessage: "Error removing user from #{stream_name}"},
                    {stream_name: sub.name},
                );
            }

            ui_report.client_error(error_message, alert_box, 1200);
        }

        if (sub.invite_only && people.is_my_user_id(target_user_id)) {
            const new_hash = hash_util.stream_edit_uri(sub);
            hide_user_profile();
            browser_history.go_to_location(new_hash);
            return;
        }
        handle_remove_stream_subscription(target_user_id, sub, removal_success, removal_failure);
    });

    $("body").on("click", "#user-profile-modal #clear_stream_search", (e) => {
        const input = $("#user-profile-streams-tab .stream-search");
        input.val("");

        // This is a hack to rerender complete
        // stream list once the text is cleared.
        input.trigger("input");

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

    $("body").on("input", "#user-profile-streams-tab .stream-search", () => {
        const input = $("#user-profile-streams-tab .stream-search");
        if (input.val().trim().length > 0) {
            $("#user-profile-streams-tab #clear_stream_search").show();
            input.css("margin-right", "-20px");
        } else {
            $("#user-profile-streams-tab #clear_stream_search").hide();
            input.css("margin-right", "0");
        }
    });
}
