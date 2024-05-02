import ClipboardJS from "clipboard";
import $ from "jquery";

import render_settings_deactivation_stream_modal from "../templates/confirm_dialog/confirm_deactivate_stream.hbs";
import render_inline_decorated_stream_name from "../templates/inline_decorated_stream_name.hbs";
import render_change_stream_info_modal from "../templates/stream_settings/change_stream_info_modal.hbs";
import render_confirm_stream_privacy_change_modal from "../templates/stream_settings/confirm_stream_privacy_change_modal.hbs";
import render_copy_email_address_modal from "../templates/stream_settings/copy_email_address_modal.hbs";
import render_stream_description from "../templates/stream_settings/stream_description.hbs";
import render_stream_settings from "../templates/stream_settings/stream_settings.hbs";

import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import {show_copied_confirmation} from "./copied_tooltip";
import * as dialog_widget from "./dialog_widget";
import * as dropdown_widget from "./dropdown_widget";
import {$t, $t_html} from "./i18n";
import * as keydown_util from "./keydown_util";
import * as narrow_state from "./narrow_state";
import * as scroll_util from "./scroll_util";
import * as settings_components from "./settings_components";
import * as settings_config from "./settings_config";
import * as settings_org from "./settings_org";
import {current_user, realm} from "./state_data";
import * as stream_color from "./stream_color";
import * as stream_data from "./stream_data";
import * as stream_edit_subscribers from "./stream_edit_subscribers";
import * as stream_edit_toggler from "./stream_edit_toggler";
import * as stream_settings_api from "./stream_settings_api";
import * as stream_settings_components from "./stream_settings_components";
import * as stream_settings_containers from "./stream_settings_containers";
import * as stream_settings_data from "./stream_settings_data";
import * as stream_ui_updates from "./stream_ui_updates";
import * as sub_store from "./sub_store";
import * as ui_report from "./ui_report";
import * as user_groups from "./user_groups";
import {user_settings} from "./user_settings";
import * as util from "./util";

export function setup_subscriptions_tab_hash(tab_key_value) {
    if ($("#subscription_overlay .right").hasClass("show")) {
        return;
    }
    if (tab_key_value === "all-streams") {
        browser_history.update("#channels/all");
    } else if (tab_key_value === "subscribed") {
        browser_history.update("#channels/subscribed");
    } else {
        blueslip.debug("Unknown tab_key_value: " + tab_key_value);
    }
}

export function get_display_text_for_realm_message_retention_setting() {
    const realm_message_retention_days = realm.realm_message_retention_days;
    if (realm_message_retention_days === settings_config.retain_message_forever) {
        return $t({defaultMessage: "(forever)"});
    }
    return $t(
        {defaultMessage: "({message_retention_days} days)"},
        {message_retention_days: realm_message_retention_days},
    );
}

function get_stream_id(target) {
    const $row = $(target).closest(
        ".stream-row, .stream_settings_header, .subscription_settings, .save-button",
    );
    return Number.parseInt($row.attr("data-stream-id"), 10);
}

function get_sub_for_target(target) {
    const stream_id = get_stream_id(target);
    if (!stream_id) {
        blueslip.error("Cannot find stream id for target");
        return undefined;
    }

    const sub = sub_store.get(stream_id);
    if (!sub) {
        blueslip.error("get_sub_for_target() failed id lookup", {stream_id});
        return undefined;
    }
    return sub;
}

export function open_edit_panel_for_row(stream_row) {
    const sub = get_sub_for_target(stream_row);

    $(".stream-row.active").removeClass("active");
    stream_settings_components.show_subs_pane.settings(sub);
    $(stream_row).addClass("active");
    setup_stream_settings(stream_row);
}

export function empty_right_panel() {
    $(".stream-row.active").removeClass("active");
    $("#subscription_overlay .right").removeClass("show");
    stream_settings_components.show_subs_pane.nothing_selected();
}

export function open_edit_panel_empty() {
    const tab_key = stream_settings_components.get_active_data().$tabs.first().attr("data-tab-key");
    empty_right_panel();
    setup_subscriptions_tab_hash(tab_key);
}

export function update_stream_name(sub, new_name) {
    const $edit_container = stream_settings_containers.get_edit_container(sub);
    $edit_container.find(".email-address").text(sub.email_address);
    $edit_container.find(".sub-stream-name").text(new_name);

    const active_data = stream_settings_components.get_active_data();
    if (active_data.id === sub.stream_id) {
        stream_settings_components.set_right_panel_title(sub);
    }
}

export function update_stream_description(sub) {
    const $edit_container = stream_settings_containers.get_edit_container(sub);
    $edit_container.find("input.description").val(sub.description);
    const html = render_stream_description({
        rendered_description: util.clean_user_content_links(sub.rendered_description),
    });
    $edit_container.find(".stream-description").html(html);
}

function show_subscription_settings(sub) {
    const $edit_container = stream_settings_containers.get_edit_container(sub);

    const $colorpicker = $edit_container.find(".colorpicker");
    const color = stream_data.get_color(sub.stream_id);
    stream_color.set_colorpicker_color($colorpicker, color);
    stream_ui_updates.update_add_subscriptions_elements(sub);

    if (!sub.render_subscribers) {
        return;
    }

    if (!stream_data.can_toggle_subscription(sub)) {
        stream_ui_updates.initialize_cant_subscribe_popover();
    }

    const $subscriber_container = $edit_container.find(".edit_subscribers_for_stream");
    stream_edit_subscribers.enable_subscriber_management({
        sub,
        $parent_container: $subscriber_container,
    });
}

function has_global_notification_setting(setting_label) {
    if (setting_label.includes("_notifications")) {
        return true;
    } else if (setting_label.includes("_notify")) {
        return true;
    }
    return false;
}

function is_notification_setting(setting_label) {
    return has_global_notification_setting(setting_label) || setting_label === "is_muted";
}

export function stream_settings(sub) {
    const settings_labels = settings_config.general_notifications_table_labels.stream;
    const check_realm_setting =
        settings_config.all_notifications(user_settings).show_push_notifications_tooltip;

    const settings = Object.keys(settings_labels).map((setting) => {
        const ret = {
            name: setting,
            label: settings_labels[setting],
            disabled_realm_setting: check_realm_setting[setting],
            is_disabled: check_realm_setting[setting],
            has_global_notification_setting: has_global_notification_setting(setting),
        };
        if (has_global_notification_setting(setting)) {
            // This block ensures we correctly display to users the
            // current state of stream-level notification settings
            // with a value of `null`, which inherit the user's global
            // notification settings for streams.
            ret.is_checked =
                stream_data.receives_notifications(sub.stream_id, setting) &&
                !check_realm_setting[setting];
            return ret;
        }
        ret.is_checked = sub[setting] && !check_realm_setting[setting];
        return ret;
    });
    return settings;
}

function setup_dropdown(sub, slim_sub) {
    const can_remove_subscribers_group_widget = new dropdown_widget.DropdownWidget({
        widget_name: "can_remove_subscribers_group",
        get_options: () =>
            user_groups.get_realm_user_groups_for_dropdown_list_widget(
                "can_remove_subscribers_group",
                "stream",
            ),
        item_click_callback(event, dropdown) {
            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
            can_remove_subscribers_group_widget.render();
            settings_components.save_discard_widget_status_handler(
                $("#stream_permission_settings"),
                false,
                slim_sub,
            );
        },
        $events_container: $("#subscription_overlay .subscription_settings"),
        tippy_props: {
            placement: "bottom-start",
        },
        default_id: sub.can_remove_subscribers_group,
        unique_id_type: dropdown_widget.DataTypes.NUMBER,
        on_mount_callback(dropdown) {
            $(dropdown.popper).css("min-width", "300px");
        },
    });
    settings_components.set_can_remove_subscribers_group_widget(
        can_remove_subscribers_group_widget,
    );
    can_remove_subscribers_group_widget.setup();
}

export function show_settings_for(node) {
    const stream_id = get_stream_id(node);
    const slim_sub = sub_store.get(stream_id);
    stream_data.clean_up_description(slim_sub);
    const sub = stream_settings_data.get_sub_for_settings(slim_sub);
    const all_settings = stream_settings(sub);

    const other_settings = [];
    const notification_settings = all_settings.filter((setting) => {
        if (is_notification_setting(setting.name)) {
            return true;
        }
        other_settings.push(setting);
        return false;
    });

    const html = render_stream_settings({
        sub,
        notification_settings,
        other_settings,
        stream_post_policy_values: settings_config.stream_post_policy_values,
        stream_privacy_policy_values: settings_config.stream_privacy_policy_values,
        stream_privacy_policy: stream_data.get_stream_privacy_policy(stream_id),
        check_default_stream: stream_data.is_default_stream_id(stream_id),
        zulip_plan_is_not_limited: realm.zulip_plan_is_not_limited,
        upgrade_text_for_wide_organization_logo: realm.upgrade_text_for_wide_organization_logo,
        is_business_type_org:
            realm.realm_org_type === settings_config.all_org_type_values.business.code,
        is_admin: current_user.is_admin,
        org_level_message_retention_setting: get_display_text_for_realm_message_retention_setting(),
        can_access_stream_email: stream_data.can_access_stream_email(sub),
    });
    scroll_util.get_content_element($("#stream_settings")).html(html);

    stream_edit_toggler.toggler.get().prependTo("#stream_settings .tab-container");
    stream_ui_updates.set_up_right_panel_section(sub);

    const $edit_container = stream_settings_containers.get_edit_container(sub);

    $(".nothing-selected").hide();
    $("#subscription_overlay .stream_change_property_info").hide();

    $edit_container.addClass("show");

    show_subscription_settings(sub);
    settings_org.set_message_retention_setting_dropdown(sub);
    stream_ui_updates.enable_or_disable_permission_settings_in_edit_panel(sub);
    setup_dropdown(sub, slim_sub);

    $("#channels_overlay_container").on(
        "click",
        ".stream-creation-confirmation-banner .main-view-banner-close-button",
        (e) => {
            e.preventDefault();
            $(e.target).parent().remove();
        },
    );
}

export function setup_stream_settings(node) {
    stream_edit_toggler.setup_toggler();
    show_settings_for(node);
}

export function update_muting_rendering(sub) {
    const $edit_container = stream_settings_containers.get_edit_container(sub);
    const $is_muted_checkbox = $edit_container.find("#sub_is_muted_setting .sub_setting_control");

    $is_muted_checkbox.prop("checked", sub.is_muted);
    $edit_container.find(".mute-note").toggleClass("hide-mute-note", !sub.is_muted);
}

function stream_notification_reset(e) {
    const sub = get_sub_for_target(e.target);
    const data = [{stream_id: sub.stream_id, property: "is_muted", value: false}];
    for (const [per_stream_setting_name, global_setting_name] of Object.entries(
        settings_config.generalize_stream_notification_setting,
    )) {
        data.push({
            stream_id: sub.stream_id,
            property: per_stream_setting_name,
            value: user_settings[global_setting_name],
        });
    }

    stream_settings_api.bulk_set_stream_property(
        data,
        $(e.target).closest(".subsection-parent").find(".alert-notification"),
    );
}

function stream_setting_changed(e) {
    const sub = get_sub_for_target(e.target);
    const $status_element = $(e.target).closest(".subsection-parent").find(".alert-notification");
    const setting = e.target.name;
    if (!sub) {
        blueslip.error("undefined sub in stream_setting_changed()");
        return;
    }
    if (has_global_notification_setting(setting) && sub[setting] === null) {
        sub[setting] =
            user_settings[settings_config.generalize_stream_notification_setting[setting]];
    }
    stream_settings_api.set_stream_property(
        sub,
        {property: setting, value: e.target.checked},
        $status_element,
    );
}

export function archive_stream(stream_id, $alert_element, $stream_row) {
    channel.del({
        url: "/json/streams/" + stream_id,
        error(xhr) {
            ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $alert_element);
        },
        success() {
            $stream_row.remove();
        },
    });
}

export function get_stream_email_address(flags, address) {
    const clean_address = address
        .replace(".show-sender", "")
        .replace(".include-footer", "")
        .replace(".include-quotes", "")
        .replace(".prefer-html", "");

    const flag_string = flags.map((flag) => "." + flag).join("");

    return clean_address.replace("@", flag_string + "@");
}

function show_stream_email_address_modal(address) {
    const copy_email_address_modal_html = render_copy_email_address_modal({
        email_address: address,
        tags: [
            {
                name: "show-sender",
                description: $t({
                    defaultMessage: "The sender's email address",
                }),
            },
            {
                name: "include-footer",
                description: $t({defaultMessage: "Email footers (e.g., signature)"}),
            },
            {
                name: "include-quotes",
                description: $t({defaultMessage: "Quoted original email (in replies)"}),
            },
            {
                name: "prefer-html",
                description: $t({
                    defaultMessage: "Use html encoding (not recommended)",
                }),
            },
        ],
    });

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Generate channel email address"}),
        html_body: copy_email_address_modal_html,
        id: "copy_email_address_modal",
        html_submit_button: $t_html({defaultMessage: "Copy address"}),
        html_exit_button: $t_html({defaultMessage: "Close"}),
        help_link: "/help/message-a-channel-by-email#configuration-options",
        on_click() {},
        close_on_submit: false,
    });
    $("#show-sender").prop("checked", true);

    const clipboard = new ClipboardJS("#copy_email_address_modal .dialog_submit_button", {
        text() {
            return address;
        },
    });

    // Show a tippy tooltip when the stream email address copied
    clipboard.on("success", (e) => {
        show_copied_confirmation(e.trigger);
    });

    $("#copy_email_address_modal .tag-checkbox").on("change", () => {
        const $checked_checkboxes = $(".copy-email-modal").find("input:checked");

        const flags = [];

        $($checked_checkboxes).each(function () {
            flags.push($(this).attr("id"));
        });

        address = get_stream_email_address(flags, address);

        $(".email-address").text(address);
    });
}

export function initialize() {
    $("#main_div").on("click", ".stream_sub_unsub_button", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const sub = narrow_state.stream_sub();
        if (sub === undefined) {
            return;
        }

        stream_settings_components.sub_or_unsub(sub);
    });

    $("#channels_overlay_container").on("click", "#open_stream_info_modal", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const stream_id = get_stream_id(e.target);
        const stream = sub_store.get(stream_id);
        const template_data = {
            stream_name: stream.name,
            stream_description: stream.description,
            max_stream_name_length: realm.max_stream_name_length,
            max_stream_description_length: realm.max_stream_description_length,
        };
        const change_stream_info_modal = render_change_stream_info_modal(template_data);
        dialog_widget.launch({
            html_heading: $t_html(
                {defaultMessage: "Edit #{channel_name}"},
                {channel_name: stream.name},
            ),
            html_body: change_stream_info_modal,
            id: "change_stream_info_modal",
            loading_spinner: true,
            on_click: save_stream_info,
            post_render() {
                $("#change_stream_info_modal .dialog_submit_button")
                    .addClass("save-button")
                    .attr("data-stream-id", stream_id);
            },
            update_submit_disabled_state_on_change: true,
        });
    });

    $("#channels_overlay_container").on("keypress", "#change_stream_description", (e) => {
        // Stream descriptions cannot be multiline, so disable enter key
        // to prevent new line
        if (keydown_util.is_enter_event(e)) {
            return false;
        }
        return true;
    });

    $("#channels_overlay_container").on(
        "click",
        ".stream-permissions-warning-banner .main-view-banner-close-button",
        (event) => {
            event.preventDefault();
            $("#stream_permission_settings .stream-permissions-warning-banner").empty();
        },
    );

    $("#channels_overlay_container").on(
        "click",
        ".stream-permissions-warning-banner .main-view-banner-action-button",
        (event) => {
            event.preventDefault();
            event.stopPropagation();

            const $target = $(event.target).parents(".main-view-banner");
            const stream_id = Number.parseInt($target.attr("data-stream-id"), 10);
            // Makes sure we take the correct stream_row.
            const $stream_row = $(
                `#channels_overlay_container div.stream-row[data-stream-id='${CSS.escape(
                    stream_id,
                )}']`,
            );
            const sub = sub_store.get(stream_id);
            stream_settings_components.sub_or_unsub(sub, $stream_row);
            $("#stream_permission_settings .stream-permissions-warning-banner").empty();
        },
    );

    function save_stream_info(e) {
        const sub = get_sub_for_target(e.currentTarget);

        const url = `/json/streams/${sub.stream_id}`;
        const data = {};
        const new_name = $("#change_stream_name").val().trim();
        const new_description = $("#change_stream_description").val().trim();

        if (new_name !== sub.name) {
            data.new_name = new_name;
        }
        if (new_description !== sub.description) {
            data.description = new_description;
        }

        dialog_widget.submit_api_request(channel.patch, url, data);
    }

    $("#channels_overlay_container").on("click", ".copy_email_button", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const stream_id = get_stream_id(e.target);

        channel.get({
            url: "/json/streams/" + stream_id + "/email_address",
            success(data) {
                const address = data.email;
                show_stream_email_address_modal(address);
            },
            error(xhr) {
                ui_report.error(
                    $t_html({defaultMessage: "Failed"}),
                    xhr,
                    $(".stream_email_address_error"),
                );
            },
        });
    });

    $("#channels_overlay_container").on(
        "click",
        ".subsection-parent .reset-stream-notifications-button",
        stream_notification_reset,
    );

    $("#channels_overlay_container").on(
        "change",
        ".sub_setting_checkbox .sub_setting_control",
        stream_setting_changed,
    );

    // This handler isn't part of the normal edit interface; it's the convenient
    // checkmark in the subscriber list.
    $("#channels_overlay_container").on("click", ".sub_unsub_button", (e) => {
        if ($(e.currentTarget).hasClass("disabled")) {
            // We do not allow users to subscribe themselves to private streams.
            return;
        }

        const sub = get_sub_for_target(e.target);
        // Makes sure we take the correct stream_row.
        const $stream_row = $(
            `#channels_overlay_container div.stream-row[data-stream-id='${CSS.escape(
                sub.stream_id,
            )}']`,
        );
        stream_settings_components.sub_or_unsub(sub, $stream_row);

        if (!sub.subscribed) {
            open_edit_panel_for_row($stream_row);
        }
        stream_ui_updates.update_regular_sub_settings(sub);

        e.preventDefault();
        e.stopPropagation();
    });

    $("#channels_overlay_container").on("click", ".deactivate", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const stream_id = get_stream_id(e.target);
        if (!stream_id) {
            ui_report.client_error(
                $t_html({defaultMessage: "Invalid channel ID"}),
                $(".stream_change_property_info"),
            );
            return;
        }

        function do_archive_stream() {
            const stream_id = Number($(".dialog_submit_button").attr("data-stream-id"));
            if (!stream_id) {
                ui_report.client_error(
                    $t_html({defaultMessage: "Invalid channel ID"}),
                    $(".stream_change_property_info"),
                );
                return;
            }
            const $row = $(".stream-row.active");
            archive_stream(stream_id, $(".stream_change_property_info"), $row);
        }

        const stream = sub_store.get(stream_id);

        const stream_name_with_privacy_symbol_html = render_inline_decorated_stream_name({stream});

        const is_new_stream_announcements_stream =
            stream_id === realm.realm_new_stream_announcements_stream_id;
        const is_signup_announcements_stream =
            stream_id === realm.realm_signup_announcements_stream_id;
        const is_zulip_update_announcements_stream =
            stream_id === realm.realm_zulip_update_announcements_stream_id;
        const is_announcement_stream =
            is_new_stream_announcements_stream ||
            is_signup_announcements_stream ||
            is_zulip_update_announcements_stream;

        const html_body = render_settings_deactivation_stream_modal({
            stream_name_with_privacy_symbol_html,
            is_new_stream_announcements_stream,
            is_signup_announcements_stream,
            is_zulip_update_announcements_stream,
            is_announcement_stream,
        });

        confirm_dialog.launch({
            html_heading: $t_html(
                {defaultMessage: "Archive <z-link></z-link>?"},
                {"z-link": () => stream_name_with_privacy_symbol_html},
            ),
            id: "archive-stream-modal",
            help_link: "/help/archive-a-channel",
            html_body,
            on_click: do_archive_stream,
        });

        $(".dialog_submit_button").attr("data-stream-id", stream_id);
    });

    $("#channels_overlay_container").on("click", ".stream-row", function (e) {
        if ($(e.target).closest(".check, .subscription_settings").length === 0) {
            open_edit_panel_for_row(this);
        }
    });

    $("#channels_overlay_container").on("change", ".stream_message_retention_setting", (e) => {
        const message_retention_setting_dropdown_value = e.target.value;
        settings_components.change_element_block_display_property(
            "stream_message_retention_custom_input",
            message_retention_setting_dropdown_value === "custom_period",
        );
    });

    $("#channels_overlay_container").on("change input", "input, select, textarea", (e) => {
        e.preventDefault();
        e.stopPropagation();

        if ($(e.target).hasClass("no-input-change-detection")) {
            // This is to prevent input changes detection in elements
            // within a subsection whose changes should not affect the
            // visibility of the discard button
            return false;
        }

        const stream_id = get_stream_id(e.target);
        const sub = sub_store.get(stream_id);
        const $subsection = $(e.target).closest(".settings-subsection-parent");
        settings_components.save_discard_widget_status_handler($subsection, false, sub);
        if (sub) {
            stream_ui_updates.update_default_stream_and_stream_privacy_state($subsection);
        }
        return true;
    });

    $("#channels_overlay_container").on(
        "click",
        ".subsection-header .subsection-changes-save button",
        (e) => {
            e.preventDefault();
            e.stopPropagation();
            const $save_button = $(e.currentTarget);
            const $subsection_elem = $save_button.closest(".settings-subsection-parent");

            const stream_id = Number(
                $save_button.closest(".subscription_settings.show").attr("data-stream-id"),
            );
            const sub = sub_store.get(stream_id);
            const data = settings_org.populate_data_for_request($subsection_elem, false, sub);

            const url = "/json/streams/" + stream_id;
            if (
                data.is_private === undefined ||
                stream_data.get_stream_privacy_policy(stream_id) !== "invite-only"
            ) {
                settings_org.save_organization_settings(data, $save_button, url);
                return;
            }
            dialog_widget.launch({
                html_heading: $t_html({defaultMessage: "Confirm changing access permissions"}),
                html_body: render_confirm_stream_privacy_change_modal,
                id: "confirm_stream_privacy_change",
                html_submit_button: $t_html({defaultMessage: "Confirm"}),
                on_click() {
                    settings_org.save_organization_settings(data, $save_button, url);
                },
                close_on_submit: true,
            });
        },
    );

    $("#channels_overlay_container").on(
        "click",
        ".subsection-header .subsection-changes-discard button",
        (e) => {
            e.preventDefault();
            e.stopPropagation();

            const stream_id = Number(
                $(e.target).closest(".subscription_settings.show").attr("data-stream-id"),
            );
            const sub = sub_store.get(stream_id);

            const $subsection = $(e.target).closest(".settings-subsection-parent");
            for (const elem of settings_components.get_subsection_property_elements($subsection)) {
                settings_org.discard_property_element_changes(elem, false, sub);
            }
            stream_ui_updates.update_default_stream_and_stream_privacy_state($subsection);
            const $save_btn_controls = $(e.target).closest(".save-button-controls");
            settings_components.change_save_button_state($save_btn_controls, "discarded");
        },
    );
}
