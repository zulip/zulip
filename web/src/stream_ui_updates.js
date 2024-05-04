import $ from "jquery";

import render_announce_stream_checkbox from "../templates/stream_settings/announce_stream_checkbox.hbs";
import render_stream_privacy_icon from "../templates/stream_settings/stream_privacy_icon.hbs";
import render_stream_settings_tip from "../templates/stream_settings/stream_settings_tip.hbs";

import * as hash_parser from "./hash_parser";
import {$t} from "./i18n";
import * as settings_components from "./settings_components";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import * as settings_org from "./settings_org";
import {current_user, realm} from "./state_data";
import * as stream_data from "./stream_data";
import * as stream_edit_toggler from "./stream_edit_toggler";
import * as stream_settings_containers from "./stream_settings_containers";
import * as sub_store from "./sub_store";

export function row_for_stream_id(stream_id) {
    return $(`.stream-row[data-stream-id='${CSS.escape(stream_id)}']`);
}

function settings_button_for_sub(sub) {
    // We don't do expectOne() here, because this button is only
    // visible if the user has that stream selected in the streams UI.
    return $(
        `.stream_settings_header[data-stream-id='${CSS.escape(sub.stream_id)}'] .subscribe-button`,
    );
}

export let subscribed_only = true;

export function is_subscribed_stream_tab_active() {
    // Returns true if "Subscribed" tab in stream settings is open
    // otherwise false.
    return subscribed_only;
}

export function set_subscribed_only(value) {
    subscribed_only = value;
}

export function update_web_public_stream_privacy_option_state($container) {
    const $web_public_stream_elem = $container.find(
        `input[value='${CSS.escape(
            settings_config.stream_privacy_policy_values.web_public.code,
        )}']`,
    );

    const for_stream_edit_panel = $container.attr("id") === "stream_permission_settings";
    if (for_stream_edit_panel) {
        const stream_id = Number.parseInt(
            $container.closest(".subscription_settings.show").attr("data-stream-id"),
            10,
        );
        const sub = sub_store.get(stream_id);
        if (!stream_data.can_change_permissions(sub)) {
            // We do not want to enable the already disabled web-public option
            // in stream-edit panel if user is not allowed to change stream
            // privacy at all.
            return;
        }
    }

    if (!realm.server_web_public_streams_enabled || !realm.realm_enable_spectator_access) {
        if (for_stream_edit_panel && $web_public_stream_elem.is(":checked")) {
            // We do not hide web-public option in the "Change privacy" modal if
            // stream is web-public already. The option is disabled in this case.
            $web_public_stream_elem.prop("disabled", true);
            return;
        }
        $web_public_stream_elem.closest(".settings-radio-input-parent").hide();
        $container
            .find(".stream-privacy-values .settings-radio-input-parent:visible")
            .last()
            .css("border-bottom", "none");
    } else {
        if (!$web_public_stream_elem.is(":visible")) {
            $container
                .find(".stream-privacy-values .settings-radio-input-parent:visible")
                .last()
                .css("border-bottom", "");
            $web_public_stream_elem.closest(".settings-radio-input-parent").show();
        }
        $web_public_stream_elem.prop(
            "disabled",
            !settings_data.user_can_create_web_public_streams(),
        );
    }
}

export function update_private_stream_privacy_option_state($container, is_default_stream = false) {
    // Disable both "Private, shared history" and "Private, protected history" options.
    const $private_stream_elem = $container.find(
        `input[value='${CSS.escape(settings_config.stream_privacy_policy_values.private.code)}']`,
    );
    const $private_with_public_history_elem = $container.find(
        `input[value='${CSS.escape(
            settings_config.stream_privacy_policy_values.private_with_public_history.code,
        )}']`,
    );

    const disable_private_stream_options =
        is_default_stream || !settings_data.user_can_create_private_streams();

    $private_stream_elem.prop("disabled", disable_private_stream_options);
    $private_with_public_history_elem.prop("disabled", disable_private_stream_options);

    $private_stream_elem
        .closest("div")
        .toggleClass("default_stream_private_tooltip", is_default_stream);
    $private_with_public_history_elem
        .closest("div")
        .toggleClass("default_stream_private_tooltip", is_default_stream);
}

export function initialize_cant_subscribe_popover() {
    const $button_wrapper = $(".settings .stream_settings_header .sub_unsub_button_wrapper");
    settings_components.initialize_disable_btn_hint_popover($button_wrapper);
}

export function set_up_right_panel_section(sub) {
    if (sub.subscribed) {
        stream_edit_toggler.toggler.enable_tab("personal");
        stream_edit_toggler.toggler.goto(stream_edit_toggler.select_tab);
    } else {
        if (stream_edit_toggler.select_tab === "personal") {
            // Go to the general settings tab, if the user is not
            // subscribed. Also preserve the previous selected tab,
            // to render next time a stream row is selected.
            stream_edit_toggler.toggler.goto("general");
        } else {
            stream_edit_toggler.toggler.goto(stream_edit_toggler.select_tab);
        }
        stream_edit_toggler.toggler.disable_tab("personal");
    }
    enable_or_disable_subscribers_tab(sub);
}

export function update_toggler_for_sub(sub) {
    if (!hash_parser.is_editing_stream(sub.stream_id)) {
        return;
    }

    set_up_right_panel_section(sub);
}

export function enable_or_disable_subscribers_tab(sub) {
    if (!hash_parser.is_editing_stream(sub.stream_id)) {
        return;
    }

    if (!stream_data.can_view_subscribers(sub)) {
        stream_edit_toggler.toggler.disable_tab("subscribers");
        if (stream_edit_toggler.select_tab === "subscribers") {
            stream_edit_toggler.toggler.goto("general");
        }
        return;
    }

    stream_edit_toggler.toggler.enable_tab("subscribers");
}

export function update_settings_button_for_sub(sub) {
    if (!hash_parser.is_editing_stream(sub.stream_id)) {
        return;
    }

    // This is for the Subscribe/Unsubscribe button in the right panel.
    const $settings_button = settings_button_for_sub(sub);

    if (!$settings_button.length) {
        // `subscribe` button hasn't been rendered yet while we are processing the event.
        return;
    }

    if (sub.subscribed) {
        $settings_button.text($t({defaultMessage: "Unsubscribe"})).removeClass("unsubscribed");
    } else {
        $settings_button.text($t({defaultMessage: "Subscribe"})).addClass("unsubscribed");
    }
    if (stream_data.can_toggle_subscription(sub)) {
        $settings_button.prop("disabled", false);
        $settings_button.parent()[0]._tippy?.destroy();
        $settings_button.css("pointer-events", "");
        $settings_button.addClass("toggle-subscription-tooltip");
    } else {
        $settings_button.attr("title", "");
        initialize_cant_subscribe_popover();
        $settings_button.prop("disabled", true);
        $settings_button.removeClass("toggle-subscription-tooltip");
    }
}

export function update_regular_sub_settings(sub) {
    // These are in the right panel.
    if (!hash_parser.is_editing_stream(sub.stream_id)) {
        return;
    }
    const $settings = $(`.subscription_settings[data-stream-id='${CSS.escape(sub.stream_id)}']`);
    if (stream_data.can_access_stream_email(sub)) {
        $settings.find(".stream-email-box").show();
    } else {
        $settings.find(".stream-email-box").hide();
    }
}

export function update_default_stream_and_stream_privacy_state($container) {
    const $default_stream = $container.find(".default-stream");
    const is_stream_creation = $container.attr("id") === "stream-creation";

    // In the stream creation UI, if the user is a non-admin hide the
    // "Default stream for new users" widget
    if (is_stream_creation && !current_user.is_admin) {
        $default_stream.hide();
        return;
    }

    const privacy_type = $container.find("input[type=radio][name=privacy]:checked").val();
    const is_invite_only =
        privacy_type === "invite-only" || privacy_type === "invite-only-public-history";

    // If a private stream option is selected, the default stream option is disabled.
    $default_stream.find("input").prop("disabled", is_invite_only);
    $default_stream.toggleClass(
        "control-label-disabled default_stream_private_tooltip",
        is_invite_only,
    );

    // If the default stream option is checked, the private stream options are disabled.
    const is_default_stream = $default_stream.find("input").prop("checked");
    update_private_stream_privacy_option_state($container, is_default_stream);
}

export function enable_or_disable_permission_settings_in_edit_panel(sub) {
    if (!hash_parser.is_editing_stream(sub.stream_id)) {
        return;
    }

    const $stream_settings = stream_settings_containers.get_edit_container(sub);

    const $general_settings_container = $stream_settings.find($("#stream_permission_settings"));
    $general_settings_container
        .find("input, select, button")
        .prop("disabled", !sub.can_change_stream_permissions);

    if (!sub.can_change_stream_permissions) {
        return;
    }

    update_default_stream_and_stream_privacy_state($stream_settings);

    const disable_message_retention_setting =
        !realm.zulip_plan_is_not_limited || !current_user.is_owner;
    $stream_settings
        .find(".stream_message_retention_setting")
        .prop("disabled", disable_message_retention_setting);
    $stream_settings
        .find(".message-retention-setting-custom-input")
        .prop("disabled", disable_message_retention_setting);

    update_web_public_stream_privacy_option_state($("#stream_permission_settings"));
}

export function update_announce_stream_option() {
    if (!hash_parser.is_create_new_stream_narrow()) {
        return;
    }
    if (stream_data.get_new_stream_announcements_stream() === "") {
        $("#announce-new-stream").hide();
        return;
    }
    $("#announce-new-stream").show();

    const new_stream_announcements_stream = stream_data.get_new_stream_announcements_stream();
    const new_stream_announcements_stream_sub = stream_data.get_sub_by_name(
        new_stream_announcements_stream,
    );
    const rendered_announce_stream = render_announce_stream_checkbox({
        new_stream_announcements_stream_sub,
    });
    $("#announce-new-stream").expectOne().html(rendered_announce_stream);
}

export function update_stream_privacy_icon_in_settings(sub) {
    if (!hash_parser.is_editing_stream(sub.stream_id)) {
        return;
    }

    const $stream_settings = stream_settings_containers.get_edit_container(sub);

    $stream_settings.find(".general_settings .large-icon").replaceWith(
        $(
            render_stream_privacy_icon({
                invite_only: sub.invite_only,
                color: sub.color,
                is_web_public: sub.is_web_public,
            }),
        ),
    );
}

export function update_permissions_banner(sub) {
    const $settings = $(`.subscription_settings[data-stream-id='${CSS.escape(sub.stream_id)}']`);

    const rendered_tip = render_stream_settings_tip(sub);
    $settings.find(".stream-settings-tip-container").html(rendered_tip);
}

export function update_notification_setting_checkbox(notification_name) {
    // This is in the right panel (Personal settings).
    const $stream_row = $("#channels_overlay_container .stream-row.active");
    if (!$stream_row.length) {
        return;
    }
    const stream_id = Number($stream_row.attr("data-stream-id"));
    $(`#${CSS.escape(notification_name)}_${CSS.escape(stream_id)}`).prop(
        "checked",
        stream_data.receives_notifications(stream_id, notification_name),
    );
}

export function update_stream_row_in_settings_tab(sub) {
    // This is in the left panel.
    // This function display/hide stream row in stream settings tab,
    // used to display immediate effect of add/removal subscription event.
    // If user is subscribed to stream, it will show sub row under
    // "Subscribed" tab, otherwise if stream is not public hide
    // stream row under tab.
    if (is_subscribed_stream_tab_active()) {
        const $sub_row = row_for_stream_id(sub.stream_id);
        if (sub.subscribed) {
            $sub_row.removeClass("notdisplayed");
        } else if (sub.invite_only || current_user.is_guest) {
            $sub_row.addClass("notdisplayed");
        }
    }
}

export function update_add_subscriptions_elements(sub) {
    if (!hash_parser.is_editing_stream(sub.stream_id)) {
        return;
    }

    // We are only concerned with the Subscribers tab for editing streams.
    const $add_subscribers_container = $(".edit_subscribers_for_stream .subscriber_list_settings");

    if (current_user.is_guest || realm.realm_is_zephyr_mirror_realm) {
        // For guest users, we just hide the add_subscribers feature.
        $add_subscribers_container.hide();
        return;
    }

    // Otherwise, we adjust whether the widgets are disabled based on
    // whether this user is authorized to add subscribers.
    const allow_user_to_add_subs = sub.can_add_subscribers;

    enable_or_disable_add_subscribers_elements($add_subscribers_container, allow_user_to_add_subs);

    if (!allow_user_to_add_subs) {
        let tooltip_message;
        if (!settings_data.user_can_subscribe_other_users()) {
            tooltip_message = $t({
                defaultMessage:
                    "You do not have permission to add other users to channels in this organization.",
            });
        } else {
            tooltip_message = $t({
                defaultMessage: "Only channel members can add users to a private channel.",
            });
        }
        settings_components.initialize_disable_btn_hint_popover(
            $add_subscribers_container,
            tooltip_message,
        );
    }
}

export function update_setting_element(sub, setting_name) {
    if (!hash_parser.is_editing_stream(sub.stream_id)) {
        return;
    }

    const $elem = $(`#id_${CSS.escape(setting_name)}`);
    settings_org.discard_property_element_changes($elem, false, sub);
}

export function enable_or_disable_add_subscribers_elements(
    $container_elem,
    enable_elem,
    stream_creation = false,
) {
    const $input_element = $container_elem.find(".input").expectOne();
    const $add_subscribers_button = $container_elem
        .find('button[name="add_subscriber"]')
        .expectOne();
    const $add_subscribers_container = $(".edit_subscribers_for_stream .subscriber_list_settings");

    $input_element.prop("contenteditable", enable_elem);
    $add_subscribers_button.prop("disabled", !enable_elem);

    if (enable_elem) {
        $add_subscribers_button.css("pointer-events", "");
        $add_subscribers_container[0]?._tippy?.destroy();
        $container_elem.find(".add_subscribers_container").removeClass("add_subscribers_disabled");
    } else {
        $container_elem.find(".add_subscribers_container").addClass("add_subscribers_disabled");
    }

    if (stream_creation) {
        const $subscribe_all_users_button = $container_elem.find("button.add_all_users_to_stream");
        $subscribe_all_users_button.prop("disabled", !enable_elem);

        if (enable_elem) {
            $container_elem
                .find(".add_all_users_to_stream_btn_container")
                .removeClass("add_subscribers_disabled");
        } else {
            $container_elem
                .find(".add_all_users_to_stream_btn_container")
                .addClass("add_subscribers_disabled");
        }
    }
}
