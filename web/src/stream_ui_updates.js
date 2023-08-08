import $ from "jquery";
import tippy from "tippy.js";

import render_announce_stream_checkbox from "../templates/stream_settings/announce_stream_checkbox.hbs";
import render_stream_privacy_icon from "../templates/stream_settings/stream_privacy_icon.hbs";
import render_stream_settings_tip from "../templates/stream_settings/stream_settings_tip.hbs";

import * as hash_util from "./hash_util";
import {$t} from "./i18n";
import {page_params} from "./page_params";
import * as settings_data from "./settings_data";
import * as settings_org from "./settings_org";
import * as stream_data from "./stream_data";
import * as stream_edit from "./stream_edit";
import * as stream_settings_containers from "./stream_settings_containers";
import * as stream_settings_ui from "./stream_settings_ui";

export function initialize_disable_btn_hint_popover($btn_wrapper, hint_text) {
    tippy($btn_wrapper[0], {
        content: hint_text,
        animation: false,
        hideOnClick: false,
        placement: "bottom",
    });
}

export function initialize_cant_subscribe_popover() {
    const $button_wrapper = $(".settings .stream_settings_header .sub_unsub_button_wrapper");
    initialize_disable_btn_hint_popover(
        $button_wrapper,
        $t({defaultMessage: "Only stream members can add users to a private stream"}),
    );
}

export function update_toggler_for_sub(sub) {
    if (!hash_util.is_editing_stream(sub.stream_id)) {
        return;
    }
    if (sub.subscribed) {
        stream_edit.toggler.enable_tab("personal_settings");
        stream_edit.toggler.goto(stream_edit.select_tab);
    } else {
        if (stream_edit.select_tab === "personal_settings") {
            // Go to the general settings tab, if the user is not
            // subscribed. Also preserve the previous selected tab,
            // to render next time a stream row is selected.
            stream_edit.toggler.goto("general_settings");
        } else {
            stream_edit.toggler.goto(stream_edit.select_tab);
        }
        stream_edit.toggler.disable_tab("personal_settings");
    }
    enable_or_disable_subscribers_tab(sub);
}

export function enable_or_disable_subscribers_tab(sub) {
    if (!hash_util.is_editing_stream(sub.stream_id)) {
        return;
    }

    if (!stream_data.can_view_subscribers(sub)) {
        stream_edit.toggler.disable_tab("subscriber_settings");
        if (stream_edit.select_tab === "subscriber_settings") {
            stream_edit.toggler.goto("general_settings");
        }
        return;
    }

    stream_edit.toggler.enable_tab("subscriber_settings");
}

export function update_settings_button_for_sub(sub) {
    if (!hash_util.is_editing_stream(sub.stream_id)) {
        return;
    }

    // This is for the Subscribe/Unsubscribe button in the right panel.
    const $settings_button = stream_settings_ui.settings_button_for_sub(sub);

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
    } else {
        $settings_button.attr("title", "");
        initialize_cant_subscribe_popover();
        $settings_button.prop("disabled", true);
    }
}

export function update_regular_sub_settings(sub) {
    // These are in the right panel.
    if (!hash_util.is_editing_stream(sub.stream_id)) {
        return;
    }
    const $settings = $(`.subscription_settings[data-stream-id='${CSS.escape(sub.stream_id)}']`);
    if (sub.subscribed) {
        $settings.find(".personal_settings").addClass("in");
        $settings.find(".stream-email-box").show();
    } else {
        $settings.find(".personal_settings").removeClass("in");
        $settings.find(".stream-email-box").hide();
    }
}

export function update_default_stream_and_stream_privacy_state($container) {
    const $default_stream = $container.find(".default-stream");
    const is_stream_creation = $container.attr("id") === "stream-creation";

    // In the stream creation UI, if the user is a non-admin hide the
    // "Default stream for new users" widget
    if (is_stream_creation && !page_params.is_admin) {
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
    stream_settings_ui.update_private_stream_privacy_option_state($container, is_default_stream);
}

export function enable_or_disable_permission_settings_in_edit_panel(sub) {
    if (!hash_util.is_editing_stream(sub.stream_id)) {
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
        !page_params.zulip_plan_is_not_limited || !page_params.is_owner;
    $stream_settings
        .find(".stream_message_retention_setting")
        .prop("disabled", disable_message_retention_setting);
    $stream_settings
        .find(".message-retention-setting-custom-input")
        .prop("disabled", disable_message_retention_setting);

    stream_settings_ui.update_web_public_stream_privacy_option_state(
        $("#stream_permission_settings"),
    );
}

export function update_announce_stream_option() {
    if (!hash_util.is_create_new_stream_narrow()) {
        return;
    }
    if (stream_data.get_notifications_stream() === "") {
        $("#announce-new-stream").hide();
        return;
    }
    $("#announce-new-stream").show();

    const notifications_stream = stream_data.get_notifications_stream();
    const notifications_stream_sub = stream_data.get_sub_by_name(notifications_stream);
    const rendered_announce_stream = render_announce_stream_checkbox({
        notifications_stream_sub,
    });
    $("#announce-new-stream").expectOne().html(rendered_announce_stream);
}

export function update_stream_privacy_icon_in_settings(sub) {
    if (!hash_util.is_editing_stream(sub.stream_id)) {
        return;
    }

    const $stream_settings = stream_settings_containers.get_edit_container(sub);

    $stream_settings.find(".general_settings .large-icon").replaceWith(
        render_stream_privacy_icon({
            invite_only: sub.invite_only,
            color: sub.color,
            is_web_public: sub.is_web_public,
        }),
    );
}

export function update_permissions_banner(sub) {
    const $settings = $(`.subscription_settings[data-stream-id='${CSS.escape(sub.stream_id)}']`);

    const rendered_tip = render_stream_settings_tip(sub);
    $settings.find(".stream-settings-tip-container").html(rendered_tip);
}

export function update_notification_setting_checkbox(notification_name) {
    // This is in the right panel (Personal settings).
    const $stream_row = $("#streams_overlay_container .stream-row.active");
    if (!$stream_row.length) {
        return;
    }
    const stream_id = $stream_row.data("stream-id");
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
    if (stream_settings_ui.is_subscribed_stream_tab_active()) {
        const $sub_row = stream_settings_ui.row_for_stream_id(sub.stream_id);
        if (sub.subscribed) {
            $sub_row.removeClass("notdisplayed");
        } else if (sub.invite_only || page_params.is_guest) {
            $sub_row.addClass("notdisplayed");
        }
    }
}

export function update_add_subscriptions_elements(sub) {
    if (!hash_util.is_editing_stream(sub.stream_id)) {
        return;
    }

    // We are only concerned with the Subscribers tab for editing streams.
    const $add_subscribers_container = $(".edit_subscribers_for_stream .subscriber_list_settings");

    if (page_params.is_guest || page_params.realm_is_zephyr_mirror_realm) {
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
                    "You do not have permission to add other users to streams in this organization.",
            });
        } else {
            tooltip_message = $t({
                defaultMessage: "Only stream members can add users to a private stream.",
            });
        }
        initialize_disable_btn_hint_popover($add_subscribers_container, tooltip_message);
    }
}

export function update_setting_element(sub, setting_name) {
    if (!hash_util.is_editing_stream(sub.stream_id)) {
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
