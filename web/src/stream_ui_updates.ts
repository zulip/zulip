import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_announce_stream_checkbox from "../templates/stream_settings/announce_stream_checkbox.hbs";
import render_stream_can_subscribe_group_label from "../templates/stream_settings/stream_can_subscribe_group_label.hbs";
import render_stream_privacy_icon from "../templates/stream_settings/stream_privacy_icon.hbs";
import render_stream_settings_tip from "../templates/stream_settings/stream_settings_tip.hbs";

import * as hash_parser from "./hash_parser.ts";
import {$t} from "./i18n.ts";
import * as overlays from "./overlays.ts";
import * as settings_components from "./settings_components.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import * as settings_org from "./settings_org.ts";
import {current_user, realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_edit_toggler from "./stream_edit_toggler.ts";
import * as stream_settings_components from "./stream_settings_components.ts";
import * as stream_settings_containers from "./stream_settings_containers.ts";
import type {SettingsSubscription} from "./stream_settings_data.ts";
import * as sub_store from "./sub_store.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as util from "./util.ts";

export function row_for_stream_id(stream_id: number): JQuery {
    return $(`.stream-row[data-stream-id='${CSS.escape(stream_id.toString())}']`);
}

function settings_button_for_sub(sub: StreamSubscription): JQuery {
    // We don't do expectOne() here, because this button is only
    // visible if the user has that stream selected in the streams UI.
    return $(
        `.stream_settings_header[data-stream-id='${CSS.escape(sub.stream_id.toString())}'] .subscribe-button`,
    );
}

export let show_subscribed = true;
export let show_not_subscribed = false;

export function is_subscribed_stream_tab_active(): boolean {
    // Returns true if "Subscribed" tab in stream settings is open
    // otherwise false.
    return show_subscribed;
}

export function is_not_subscribed_stream_tab_active(): boolean {
    // Returns true if "not-subscribed" tab in stream settings is open
    // otherwise false.
    return show_not_subscribed;
}

export function set_show_subscribed(value: boolean): void {
    show_subscribed = value;
}

export function set_show_not_subscribed(value: boolean): void {
    show_not_subscribed = value;
}

export function update_web_public_stream_privacy_option_state($container: JQuery): void {
    const $web_public_stream_elem = $container.find(
        `input[value='${CSS.escape(
            settings_config.stream_privacy_policy_values.web_public.code,
        )}']`,
    );

    const for_stream_edit_panel = $container.attr("id") === "stream_permission_settings";
    if (for_stream_edit_panel) {
        const stream_id = Number.parseInt(
            $container.closest(".subscription_settings.show").attr("data-stream-id")!,
            10,
        );
        const sub = sub_store.get(stream_id);
        assert(sub !== undefined);
        if (!stream_data.can_change_permissions_requiring_content_access(sub)) {
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

export function update_private_stream_privacy_option_state(
    $container: JQuery,
    is_default_stream = false,
): void {
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

export function initialize_cant_subscribe_popover(): void {
    const $button_wrapper = $(".settings .stream_settings_header .sub_unsub_button_wrapper");
    settings_components.initialize_disable_button_hint_popover($button_wrapper, undefined);
}

export function set_up_right_panel_section(sub: StreamSubscription): void {
    if (sub.subscribed && !sub.is_archived) {
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

export function update_toggler_for_sub(sub: StreamSubscription): void {
    if (!hash_parser.is_editing_stream(sub.stream_id)) {
        return;
    }

    set_up_right_panel_section(sub);
}

export function enable_or_disable_subscribers_tab(sub: StreamSubscription): void {
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

export function update_settings_button_for_sub(sub: StreamSubscription): void {
    if (!hash_parser.is_editing_stream(sub.stream_id)) {
        return;
    }

    // This is for the Subscribe/Unsubscribe button in the right panel.
    const $settings_button = settings_button_for_sub(sub);

    if ($settings_button.length === 0) {
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
        const $parent_element: tippy.ReferenceElement & HTMLElement = util.the(
            $settings_button.parent(),
        );
        $parent_element._tippy?.destroy();
        $settings_button.css("pointer-events", "");
        $settings_button.addClass("toggle-subscription-tooltip");
    } else {
        $settings_button.attr("title", "");
        initialize_cant_subscribe_popover();
        $settings_button.prop("disabled", true);
        $settings_button.removeClass("toggle-subscription-tooltip");
    }
}

export function update_regular_sub_settings(sub: StreamSubscription): void {
    // These are in the right panel.
    if (!hash_parser.is_editing_stream(sub.stream_id)) {
        return;
    }
    const $settings = $(
        `.subscription_settings[data-stream-id='${CSS.escape(sub.stream_id.toString())}']`,
    );
    if (stream_data.can_access_stream_email(sub)) {
        $settings.find(".stream-email-box").show();
    } else {
        $settings.find(".stream-email-box").hide();
    }
}

export function update_default_stream_and_stream_privacy_state($container: JQuery): void {
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
    const is_default_stream = util.the($default_stream.find("input")).checked;
    update_private_stream_privacy_option_state($container, is_default_stream);
}

export function update_can_subscribe_group_label($container: JQuery): void {
    const privacy_type = $container.find("input[type=radio][name=privacy]:checked").val();
    const is_invite_only =
        privacy_type === "invite-only" || privacy_type === "invite-only-public-history";

    const $can_subscribe_group_label = $container.find(".can_subscribe_group_label");
    $can_subscribe_group_label.html(render_stream_can_subscribe_group_label({is_invite_only}));
}

export function enable_or_disable_permission_settings_in_edit_panel(
    sub: SettingsSubscription,
): void {
    if (!hash_parser.is_editing_stream(sub.stream_id)) {
        return;
    }

    const $stream_settings = stream_settings_containers.get_edit_container(sub);

    const $general_settings_container = $stream_settings.find($("#stream_permission_settings"));
    $general_settings_container
        .find("input, button")
        .prop("disabled", !sub.can_change_stream_permissions_requiring_metadata_access);

    const $advanced_configurations_container = $stream_settings.find(
        $("#stream-advanced-configurations"),
    );
    $advanced_configurations_container
        .find("input, select, button")
        .prop("disabled", !sub.can_change_stream_permissions_requiring_metadata_access);

    const $permission_pill_container_elements =
        $advanced_configurations_container.find(".pill-container");
    $permission_pill_container_elements
        .find(".input")
        .prop("contenteditable", sub.can_change_stream_permissions_requiring_metadata_access);

    if (!sub.can_change_stream_permissions_requiring_metadata_access) {
        $general_settings_container.find(".default-stream").addClass("control-label-disabled");
        $permission_pill_container_elements
            .closest(".input-group")
            .addClass("group_setting_disabled");
        settings_components.disable_opening_typeahead_on_clicking_label(
            $advanced_configurations_container,
        );
        return;
    }

    $permission_pill_container_elements
        .closest(".input-group")
        .removeClass("group_setting_disabled");
    settings_components.enable_opening_typeahead_on_clicking_label(
        $advanced_configurations_container,
    );

    update_default_stream_and_stream_privacy_state($stream_settings);

    const disable_message_retention_setting =
        !realm.zulip_plan_is_not_limited || !current_user.is_owner;
    $stream_settings
        .find(".stream_message_retention_setting")
        .prop("disabled", disable_message_retention_setting);
    $stream_settings
        .find(".message-retention-setting-custom-input")
        .prop("disabled", disable_message_retention_setting);

    const $stream_permission_settings = $("#stream_permission_settings");

    update_web_public_stream_privacy_option_state($stream_permission_settings);
    update_public_stream_privacy_option_state($stream_permission_settings);

    if (!sub.can_change_stream_permissions_requiring_content_access) {
        const $stream_privacy_values = $stream_settings
            .find($(".stream-privacy-values"))
            .find("input, button");
        $stream_privacy_values.prop("disabled", true);

        for (const setting_name of settings_config.stream_group_permission_settings_requiring_content_access) {
            const $setting_element = $advanced_configurations_container.find("#id_" + setting_name);
            $setting_element.find(".input").prop("contenteditable", false);
            $setting_element.closest(".input-group").addClass("group_setting_disabled");
            settings_components.disable_opening_typeahead_on_clicking_label($setting_element);
        }
    }
}

export function update_announce_stream_option(): void {
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

export function update_stream_privacy_icon_in_settings(sub: StreamSubscription): void {
    if (!hash_parser.is_editing_stream(sub.stream_id)) {
        return;
    }

    const $stream_settings = stream_settings_containers.get_edit_container(sub);

    $stream_settings.find(".stream_section[data-stream-section='general'] .large-icon").replaceWith(
        $(
            render_stream_privacy_icon({
                invite_only: sub.invite_only,
                color: sub.color,
                is_web_public: sub.is_web_public,
                is_archived: sub.is_archived,
            }),
        ),
    );
}

export function update_permissions_banner(sub: StreamSubscription): void {
    const $settings = $(
        `.subscription_settings[data-stream-id='${CSS.escape(sub.stream_id.toString())}']`,
    );

    const rendered_tip = render_stream_settings_tip(sub);
    $settings.find(".stream-settings-tip-container").html(rendered_tip);
}

export function update_notification_setting_checkbox(
    notification_name: keyof sub_store.StreamSpecificNotificationSettings,
): void {
    // This is in the right panel (Personal settings).
    const $stream_row = $("#channels_overlay_container .stream-row.active");
    if ($stream_row.length === 0) {
        return;
    }
    const stream_id = Number($stream_row.attr("data-stream-id"));
    $(`#${CSS.escape(notification_name)}_${CSS.escape(stream_id.toString())}`).prop(
        "checked",
        stream_data.receives_notifications(stream_id, notification_name),
    );
}

export function update_stream_row_in_settings_tab(sub: StreamSubscription): void {
    // This is in the left panel.
    // This function display/hide stream row in stream settings tab,
    // used to display immediate effect of add/removal subscription event.
    // If user is subscribed or unsubscribed to stream, it will show sub or unsub
    // row under "Subscribed" or "Not subscribed" (only if the stream is public) tab, otherwise
    // if stream is not public hide stream row under tab.

    if (is_subscribed_stream_tab_active() || is_not_subscribed_stream_tab_active()) {
        const $row = row_for_stream_id(sub.stream_id);

        if (
            (is_subscribed_stream_tab_active() && sub.subscribed) ||
            (is_not_subscribed_stream_tab_active() && !sub.subscribed)
        ) {
            if (stream_settings_components.filter_includes_channel(sub)) {
                $row.removeClass("notdisplayed");
            }
        } else if (sub.invite_only || current_user.is_guest) {
            $row.addClass("notdisplayed");
        }
    }
}

export function update_add_subscriptions_elements(sub: SettingsSubscription): void {
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
        if (!settings_data.can_subscribe_others_to_all_accessible_streams()) {
            tooltip_message = $t({
                defaultMessage:
                    "You do not have permission to add other users to channels in this organization.",
            });
        } else {
            tooltip_message = $t({
                defaultMessage: "You do not have permission to add other users to this channel.",
            });
        }
        settings_components.initialize_disable_button_hint_popover(
            $add_subscribers_container,
            tooltip_message,
        );
    }
}

export function update_setting_element(sub: StreamSubscription, setting_name: string): void {
    if (!hash_parser.is_editing_stream(sub.stream_id)) {
        return;
    }

    const $elem = $(`#id_${CSS.escape(setting_name)}`);
    const $subsection = $elem.closest(".settings-subsection-parent");
    if ($subsection.find(".save-button-controls").hasClass("hide")) {
        settings_org.discard_stream_property_element_changes(util.the($elem), sub);
    } else {
        settings_org.discard_stream_settings_subsection_changes($subsection, sub);
    }
}

export function enable_or_disable_add_subscribers_elements(
    $container_elem: JQuery,
    enable_elem: boolean,
    stream_creation = false,
): void {
    const $input_element = $container_elem.find(".input").expectOne();
    const $add_subscribers_container = $<tippy.PopperElement>(
        ".edit_subscribers_for_stream .subscriber_list_settings",
    );

    $input_element.prop("contenteditable", enable_elem);

    if (enable_elem) {
        $add_subscribers_container[0]?._tippy?.destroy();
        $container_elem.find(".add_subscribers_container").removeClass("add_subscribers_disabled");
    } else {
        $container_elem.find(".add_subscribers_container").addClass("add_subscribers_disabled");
    }

    if (!stream_creation) {
        const $add_subscribers_button = $container_elem.find(".add-subscriber-button").expectOne();
        const input_empty =
            $container_elem.find(".pill").length === 0 && $input_element.text().length === 0;
        $add_subscribers_button.prop("disabled", !enable_elem || input_empty);
        if (enable_elem) {
            $add_subscribers_button.css("pointer-events", "");
        }
    }
}

export function update_public_stream_privacy_option_state($container: JQuery): void {
    const $public_stream_elem = $container.find(
        `input[value='${CSS.escape(settings_config.stream_privacy_policy_values.public.code)}']`,
    );
    $public_stream_elem.prop("disabled", !settings_data.user_can_create_public_streams());
}

export function hide_or_disable_stream_privacy_options_if_required($container: JQuery): void {
    update_web_public_stream_privacy_option_state($container);

    update_public_stream_privacy_option_state($container);

    update_private_stream_privacy_option_state($container);
}

export function update_stream_privacy_choices(policy: string): void {
    if (!overlays.streams_open()) {
        return;
    }
    const stream_edit_panel_opened = $("#stream_permission_settings").is(":visible");
    const stream_creation_form_opened = $("#stream-creation").is(":visible");

    if (!stream_edit_panel_opened && !stream_creation_form_opened) {
        return;
    }
    let $container = $("#stream-creation");
    if (stream_edit_panel_opened) {
        $container = $("#stream_permission_settings");
    }

    if (policy === "can_create_private_channel_group") {
        update_private_stream_privacy_option_state($container);
    }
    if (policy === "can_create_public_channel_group") {
        update_public_stream_privacy_option_state($container);
    }
    if (policy === "can_create_web_public_channel_group") {
        update_web_public_stream_privacy_option_state($container);
    }
}
