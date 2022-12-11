import ClipboardJS from "clipboard";
import $ from "jquery";

import render_settings_deactivation_stream_modal from "../templates/confirm_dialog/confirm_deactivate_stream.hbs";
import render_stream_privacy from "../templates/stream_privacy.hbs";
import render_change_stream_info_modal from "../templates/stream_settings/change_stream_info_modal.hbs";
import render_copy_email_address_modal from "../templates/stream_settings/copy_email_address_modal.hbs";
import render_stream_description from "../templates/stream_settings/stream_description.hbs";
import render_stream_settings from "../templates/stream_settings/stream_settings.hbs";

import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as channel from "./channel";
import * as components from "./components";
import * as confirm_dialog from "./confirm_dialog";
import * as dialog_widget from "./dialog_widget";
import * as hash_util from "./hash_util";
import {$t, $t_html} from "./i18n";
import * as keydown_util from "./keydown_util";
import * as narrow_state from "./narrow_state";
import {page_params} from "./page_params";
import * as settings_config from "./settings_config";
import * as settings_org from "./settings_org";
import * as settings_ui from "./settings_ui";
import * as stream_color from "./stream_color";
import * as stream_data from "./stream_data";
import * as stream_edit_subscribers from "./stream_edit_subscribers";
import * as stream_settings_containers from "./stream_settings_containers";
import * as stream_settings_data from "./stream_settings_data";
import * as stream_settings_ui from "./stream_settings_ui";
import * as stream_ui_updates from "./stream_ui_updates";
import * as sub_store from "./sub_store";
import * as ui from "./ui";
import * as ui_report from "./ui_report";
import {user_settings} from "./user_settings";
import * as util from "./util";

export let toggler;
export let select_tab = "personal_settings";

function setup_subscriptions_stream_hash(sub) {
    const hash = hash_util.stream_edit_url(sub);
    browser_history.update(hash);
}

export function setup_subscriptions_tab_hash(tab_key_value) {
    if (tab_key_value === "all-streams") {
        browser_history.update("#streams/all");
    } else if (tab_key_value === "subscribed") {
        browser_history.update("#streams/subscribed");
    } else {
        blueslip.debug("Unknown tab_key_value: " + tab_key_value);
    }
}

export function get_display_text_for_realm_message_retention_setting() {
    const realm_message_retention_days = page_params.realm_message_retention_days;
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
        blueslip.error("get_sub_for_target() failed id lookup: " + stream_id);
        return undefined;
    }
    return sub;
}

export function open_edit_panel_for_row(stream_row) {
    const sub = get_sub_for_target(stream_row);

    $(".stream-row.active").removeClass("active");
    stream_settings_ui.show_subs_pane.settings(sub);
    $(stream_row).addClass("active");
    setup_subscriptions_stream_hash(sub);
    setup_stream_settings(stream_row);
}

export function open_edit_panel_empty() {
    const tab_key = stream_settings_ui.get_active_data().$tabs.first().attr("data-tab-key");
    $(".stream-row.active").removeClass("active");
    stream_settings_ui.show_subs_pane.nothing_selected();
    setup_subscriptions_tab_hash(tab_key);
}

export function update_stream_name(sub, new_name) {
    const $edit_container = stream_settings_containers.get_edit_container(sub);
    $edit_container.find(".email-address").text(sub.email_address);
    $edit_container.find(".sub-stream-name").text(new_name);

    const active_data = stream_settings_ui.get_active_data();
    if (active_data.id === sub.stream_id) {
        stream_settings_ui.set_right_panel_title(sub);
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
    const color = stream_data.get_color(sub.name);
    stream_color.set_colorpicker_color($colorpicker, color);
    stream_ui_updates.update_add_subscriptions_elements(sub);

    if (!sub.render_subscribers) {
        return;
    }

    if (!stream_data.can_toggle_subscription(sub)) {
        stream_ui_updates.initialize_cant_subscribe_popover(sub);
    }

    const $subscriber_container = $edit_container.find(".edit_subscribers_for_stream");
    stream_edit_subscribers.enable_subscriber_management({
        sub,
        $parent_container: $subscriber_container,
    });
}

export function is_notification_setting(setting_label) {
    if (setting_label.includes("_notifications")) {
        return true;
    } else if (setting_label.includes("_notify")) {
        return true;
    }
    return false;
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
            is_notification_setting: is_notification_setting(setting),
        };
        if (is_notification_setting(setting)) {
            // This block ensures we correctly display to users the
            // current state of stream-level notification settings
            // with a value of `null`, which inherit the user's global
            // notification settings for streams.
            ret.is_checked =
                stream_data.receives_notifications(sub.stream_id, setting) &&
                !check_realm_setting[setting];
            ret.is_disabled = ret.is_disabled || sub.is_muted;
            return ret;
        }
        ret.is_checked = sub[setting] && !check_realm_setting[setting];
        return ret;
    });
    return settings;
}

export function show_settings_for(node) {
    const stream_id = get_stream_id(node);
    const slim_sub = sub_store.get(stream_id);
    stream_data.clean_up_description(slim_sub);
    const sub = stream_settings_data.get_sub_for_settings(slim_sub);
    const all_settings = stream_settings(sub);

    const other_settings = [];
    const notification_settings = all_settings.filter((setting) => {
        if (setting.is_notification_setting) {
            return true;
        }
        other_settings.push(setting);
        return false;
    });

    const html = render_stream_settings({
        sub,
        notification_settings,
        other_settings,
        stream_post_policy_values: stream_data.stream_post_policy_values,
        stream_privacy_policy_values: stream_data.stream_privacy_policy_values,
        stream_privacy_policy: stream_data.get_stream_privacy_policy(stream_id),
        zulip_plan_is_not_limited: page_params.zulip_plan_is_not_limited,
        upgrade_text_for_wide_organization_logo:
            page_params.upgrade_text_for_wide_organization_logo,
        is_admin: page_params.is_admin,
        org_level_message_retention_setting: get_display_text_for_realm_message_retention_setting(),
    });
    ui.get_content_element($("#stream_settings")).html(html);

    $("#stream_settings .tab-container").prepend(toggler.get());
    stream_ui_updates.update_toggler_for_sub(sub);

    const $edit_container = stream_settings_containers.get_edit_container(sub);

    $(".nothing-selected").hide();
    $("#subscription_overlay .stream_change_property_info").hide();

    $edit_container.addClass("show");

    show_subscription_settings(sub);
    settings_org.set_message_retention_setting_dropdown(sub);
    stream_ui_updates.enable_or_disable_permission_settings_in_edit_panel(sub);
}

export function setup_stream_settings(node) {
    toggler = components.toggle({
        child_wants_focus: true,
        values: [
            {label: $t({defaultMessage: "General"}), key: "general_settings"},
            {label: $t({defaultMessage: "Personal"}), key: "personal_settings"},
            {label: $t({defaultMessage: "Subscribers"}), key: "subscriber_settings"},
        ],
        callback(name, key) {
            $(".stream_section").hide();
            $("." + key).show();
            select_tab = key;
        },
    });

    show_settings_for(node);
}

export function update_muting_rendering(sub) {
    const $edit_container = stream_settings_containers.get_edit_container(sub);
    const $notification_checkboxes = $edit_container.find(".sub_notification_setting");
    const $is_muted_checkbox = $edit_container.find("#sub_is_muted_setting .sub_setting_control");

    $is_muted_checkbox.prop("checked", sub.is_muted);
    $edit_container.find(".mute-note").toggleClass("hide-mute-note", !sub.is_muted);
    $notification_checkboxes.toggleClass("muted-sub", sub.is_muted);
    $notification_checkboxes.find("input[type='checkbox']").prop("disabled", sub.is_muted);
}

function stream_is_muted_changed(e) {
    const sub = get_sub_for_target(e.target);
    if (!sub) {
        blueslip.error("stream_is_muted_changed() fails");
        return;
    }

    stream_settings_ui.set_muted(
        sub,
        e.target.checked,
        `#stream_change_property_status${CSS.escape(sub.stream_id)}`,
    );
}

export function stream_setting_changed(e, from_notification_settings) {
    if (e.target.name === "is_muted") {
        return;
    }

    const sub = get_sub_for_target(e.target);
    const status_element = from_notification_settings
        ? $(e.target).closest(".subsection-parent").find(".alert-notification")
        : $(`#stream_change_property_status${CSS.escape(sub.stream_id)}`);
    const setting = e.target.name;
    if (!sub) {
        blueslip.error("undefined sub in stream_setting_changed()");
        return;
    }
    if (is_notification_setting(setting) && sub[setting] === null) {
        sub[setting] =
            user_settings[settings_config.generalize_stream_notification_setting[setting]];
    }
    set_stream_property(sub, setting, e.target.checked, status_element);
}

export function bulk_set_stream_property(sub_data, status_element) {
    const url = "/json/users/me/subscriptions/properties";
    const data = {subscription_data: JSON.stringify(sub_data)};
    if (!status_element) {
        return channel.post({
            url,
            data,
            timeout: 10 * 1000,
        });
    }

    settings_ui.do_settings_change(channel.post, url, data, status_element);
    return undefined;
}

export function set_stream_property(sub, property, value, status_element) {
    const sub_data = {stream_id: sub.stream_id, property, value};
    bulk_set_stream_property([sub_data], status_element);
}

export function get_request_data_for_stream_privacy(selected_val) {
    switch (selected_val) {
        case stream_data.stream_privacy_policy_values.public.code: {
            return {
                is_private: false,
                history_public_to_subscribers: true,
                is_web_public: false,
            };
        }
        case stream_data.stream_privacy_policy_values.private.code: {
            return {
                is_private: true,
                history_public_to_subscribers: false,
                is_web_public: false,
            };
        }
        case stream_data.stream_privacy_policy_values.web_public.code: {
            return {
                is_private: false,
                history_public_to_subscribers: true,
                is_web_public: true,
            };
        }
        default: {
            return {
                is_private: true,
                history_public_to_subscribers: true,
                is_web_public: false,
            };
        }
    }
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

export function initialize() {
    $("#main_div").on("click", ".stream_sub_unsub_button", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const sub = narrow_state.stream_sub();
        if (sub === undefined) {
            return;
        }

        stream_settings_ui.sub_or_unsub(sub);
    });

    $("#manage_streams_container").on("click", "#open_stream_info_modal", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const stream_id = get_stream_id(e.target);
        const stream = sub_store.get(stream_id);
        const template_data = {
            stream_name: stream.name,
            stream_description: stream.description,
            max_stream_name_length: page_params.max_stream_name_length,
            max_stream_description_length: page_params.max_stream_description_length,
        };
        const change_stream_info_modal = render_change_stream_info_modal(template_data);
        dialog_widget.launch({
            html_heading: $t_html(
                {defaultMessage: "Edit #{stream_name}"},
                {stream_name: stream.name},
            ),
            html_body: change_stream_info_modal,
            id: "change_stream_info_modal",
            on_click: save_stream_info,
            post_render() {
                $("#change_stream_info_modal .dialog_submit_button")
                    .addClass("save-button")
                    .attr("data-stream-id", stream_id);
            },
        });
    });

    $("#manage_streams_container").on("keypress", "#change_stream_description", (e) => {
        // Stream descriptions can not be multiline, so disable enter key
        // to prevent new line
        if (keydown_util.is_enter_event(e)) {
            return false;
        }
        return true;
    });

    function save_stream_info(e) {
        e.preventDefault();
        e.stopPropagation();
        const sub = get_sub_for_target(e.currentTarget);

        const url = `/json/streams/${sub.stream_id}`;
        const data = {};
        const new_name = $("#change_stream_name").val().trim();
        const new_description = $("#change_stream_description").val().trim();

        if (new_name === sub.name && new_description === sub.description) {
            return;
        }
        if (new_name !== sub.name) {
            data.new_name = new_name;
        }
        if (new_description !== sub.description) {
            data.description = new_description;
        }

        const $status_element = $(".stream_change_property_info");
        dialog_widget.close_modal();
        settings_ui.do_settings_change(channel.patch, url, data, $status_element);
    }

    $("#manage_streams_container").on("click", ".copy_email_button", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const stream_id = get_stream_id(e.target);
        const stream = sub_store.get(stream_id);
        let address = stream.email_address;

        const copy_email_address = render_copy_email_address_modal({
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
            html_heading: $t_html({defaultMessage: "Generate stream email address"}),
            html_body: copy_email_address,
            id: "copy_email_address_modal",
            html_submit_button: $t_html({defaultMessage: "Copy address"}),
            help_link: "/help/message-a-stream-by-email#configuration-options",
            on_click() {},
            close_on_submit: true,
        });
        $("#show-sender").prop("checked", true);

        new ClipboardJS("#copy_email_address_modal .dialog_submit_button", {
            text() {
                return address;
            },
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
    });

    $("#manage_streams_container").on(
        "change",
        "#sub_is_muted_setting .sub_setting_control",
        stream_is_muted_changed,
    );

    $("#manage_streams_container").on(
        "change",
        ".sub_setting_checkbox .sub_setting_control",
        stream_setting_changed,
    );

    // This handler isn't part of the normal edit interface; it's the convenient
    // checkmark in the subscriber list.
    $("#manage_streams_container").on("click", ".sub_unsub_button", (e) => {
        const sub = get_sub_for_target(e.target);
        // Makes sure we take the correct stream_row.
        const $stream_row = $(
            `#manage_streams_container div.stream-row[data-stream-id='${CSS.escape(
                sub.stream_id,
            )}']`,
        );
        stream_settings_ui.sub_or_unsub(sub, $stream_row);

        if (!sub.subscribed) {
            open_edit_panel_for_row($stream_row);
        }
        stream_ui_updates.update_regular_sub_settings(sub);

        e.preventDefault();
        e.stopPropagation();
    });

    $("#manage_streams_container").on("click", ".deactivate", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const stream_id = get_stream_id(e.target);
        if (!stream_id) {
            ui_report.client_error(
                $t_html({defaultMessage: "Invalid stream ID"}),
                $(".stream_change_property_info"),
            );
            return;
        }

        function do_archive_stream() {
            const stream_id = $(".dialog_submit_button").data("stream-id");
            if (!stream_id) {
                ui_report.client_error(
                    $t_html({defaultMessage: "Invalid stream ID"}),
                    $(".stream_change_property_info"),
                );
                return;
            }
            const $row = $(".stream-row.active");
            archive_stream(stream_id, $(".stream_change_property_info"), $row);
        }

        const stream = sub_store.get(stream_id);
        const stream_privacy_symbol_html = render_stream_privacy({
            invite_only: stream.invite_only,
            is_web_public: stream.is_web_public,
        });
        const stream_name = stream_data.maybe_get_stream_name(stream_id);
        const html_body = render_settings_deactivation_stream_modal({
            stream_name,
            stream_privacy_symbol_html,
        });

        confirm_dialog.launch({
            html_heading: $t_html(
                {defaultMessage: "Archive <z-link></z-link>{stream}?"},
                {stream: stream_name, "z-link": () => stream_privacy_symbol_html},
            ),
            id: "archive-stream-modal",
            help_link: "/help/archive-a-stream",
            html_body,
            on_click: do_archive_stream,
        });

        $(".dialog_submit_button").attr("data-stream-id", stream_id);
    });

    $("#manage_streams_container").on("click", ".stream-row", function (e) {
        if ($(e.target).closest(".check, .subscription_settings").length === 0) {
            open_edit_panel_for_row(this);
        }
    });

    $("#manage_streams_container").on("change", ".stream_message_retention_setting", (e) => {
        const message_retention_setting_dropdown_value = e.target.value;
        settings_org.change_element_block_display_property(
            "stream_message_retention_custom_input",
            message_retention_setting_dropdown_value === "custom_period",
        );
    });

    $("#manage_streams_container").on("change input", "input, select, textarea", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const stream_id = get_stream_id(e.target);
        const sub = sub_store.get(stream_id);
        const $subsection = $(e.target).closest(".settings-subsection-parent");
        settings_org.save_discard_widget_status_handler($subsection, false, sub);
    });

    $("#manage_streams_container").on(
        "click",
        ".subsection-header .subsection-changes-save button",
        (e) => {
            e.preventDefault();
            e.stopPropagation();
            const $save_button = $(e.currentTarget);
            const $subsection_elem = $save_button.closest(".settings-subsection-parent");

            const stream_id = $save_button.closest(".subscription_settings.show").data("stream-id");
            const sub = sub_store.get(stream_id);
            const data = settings_org.populate_data_for_request($subsection_elem, false, sub);

            const url = "/json/streams/" + stream_id;
            settings_org.save_organization_settings(data, $save_button, url);
        },
    );

    $("#manage_streams_container").on(
        "click",
        ".subsection-header .subsection-changes-discard button",
        (e) => {
            e.preventDefault();
            e.stopPropagation();

            const stream_id = $(e.target).closest(".subscription_settings.show").data("stream-id");
            const sub = sub_store.get(stream_id);

            const $subsection = $(e.target).closest(".settings-subsection-parent");
            for (const elem of settings_org.get_subsection_property_elements($subsection)) {
                settings_org.discard_property_element_changes(elem, false, sub);
            }
            const $save_btn_controls = $(e.target).closest(".save-button-controls");
            settings_org.change_save_button_state($save_btn_controls, "discarded");
        },
    );
}
