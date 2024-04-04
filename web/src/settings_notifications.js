import $ from "jquery";

import render_confirm_disable_all_notifications from "../templates/confirm_dialog/confirm_disable_all_notifications.hbs";
import render_stream_specific_notification_row from "../templates/settings/stream_specific_notification_row.hbs";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import {$t, $t_html} from "./i18n";
import * as message_notifications from "./message_notifications";
import {page_params} from "./page_params";
import * as settings_components from "./settings_components";
import * as settings_config from "./settings_config";
import * as settings_ui from "./settings_ui";
import {realm} from "./state_data";
import * as stream_data from "./stream_data";
import * as stream_settings_api from "./stream_settings_api";
import * as stream_settings_data from "./stream_settings_data";
import * as sub_store from "./sub_store";
import * as ui_util from "./ui_util";
import * as unread_ui from "./unread_ui";
import {user_settings} from "./user_settings";

export const user_settings_panel = {};

function rerender_ui() {
    const $unmatched_streams_table = $("#stream-specific-notify-table");
    if ($unmatched_streams_table.length === 0) {
        // If we haven't rendered "notification settings" yet, do nothing.
        return;
    }

    const unmatched_streams =
        stream_settings_data.get_unmatched_streams_for_notification_settings();

    $unmatched_streams_table.find(".stream-notifications-row").remove();

    const muted_stream_ids = stream_data.muted_stream_ids();

    for (const stream of unmatched_streams) {
        $unmatched_streams_table.append(
            $(
                render_stream_specific_notification_row({
                    stream,
                    stream_specific_notification_settings:
                        settings_config.stream_specific_notification_settings,
                    is_disabled:
                        settings_config.all_notifications(user_settings)
                            .show_push_notifications_tooltip,
                    muted: muted_stream_ids.includes(stream.stream_id),
                }),
            ),
        );
    }

    if (unmatched_streams.length === 0) {
        $unmatched_streams_table.css("display", "none");
    } else {
        $unmatched_streams_table.css("display", "table-row-group");
    }
}

function change_notification_setting(setting, value, $status_element) {
    const data = {};
    data[setting] = value;
    settings_ui.do_settings_change(channel.patch, "/json/settings", data, $status_element);
}

function update_desktop_icon_count_display(settings_panel) {
    const $container = $(settings_panel.container);
    const settings_object = settings_panel.settings_object;
    $container
        .find(".setting_desktop_icon_count_display")
        .val(settings_object.desktop_icon_count_display);
    if (!settings_panel.for_realm_settings) {
        unread_ui.update_unread_counts();
    }
}

export function set_notification_batching_ui($container, setting_seconds, force_custom) {
    const $edit_elem = $container.find(".email_notification_batching_period_edit_minutes");
    const valid_period_values = settings_config.email_notifications_batching_period_values.map(
        (x) => x.value,
    );

    // We display the custom widget if either the user just selected
    // custom_period, or the current value cannot be represented with
    // the existing set of values.
    const show_edit_elem = force_custom || !valid_period_values.includes(setting_seconds);
    const select_elem_val = show_edit_elem ? "custom_period" : setting_seconds;

    $container.find(".setting_email_notifications_batching_period_seconds").val(select_elem_val);
    $edit_elem.val(setting_seconds / 60);
    settings_components.change_element_block_display_property(
        $edit_elem.attr("id"),
        show_edit_elem,
    );
}

export function set_enable_digest_emails_visibility($container, for_realm_settings) {
    if (realm.realm_digest_emails_enabled) {
        if (for_realm_settings) {
            $container.find(".other_email_notifications").show();
            return;
        }
        $container.find(".enable_digest_emails_label").parent().show();
    } else {
        if (for_realm_settings) {
            $container.find(".other_email_notifications").hide();
            return;
        }
        $container.find(".enable_digest_emails_label").parent().hide();
    }
}

export function set_enable_marketing_emails_visibility() {
    const $container = $("#user-notification-settings");
    if (page_params.corporate_enabled) {
        $container.find(".enable_marketing_emails_label").parent().show();
    } else {
        $container.find(".enable_marketing_emails_label").parent().hide();
    }
}

function stream_notification_setting_changed(e) {
    const $row = $(e.target).closest(".stream-notifications-row");
    const stream_id = Number.parseInt($row.attr("data-stream-id"), 10);
    if (!stream_id) {
        blueslip.error("Cannot find stream id for target");
        return;
    }

    const sub = sub_store.get(stream_id);
    if (!sub) {
        blueslip.error("stream_notification_setting_changed() failed id lookup", {stream_id});
        return;
    }

    const $status_element = $(e.target).closest(".subsection-parent").find(".alert-notification");
    const setting = e.target.name;
    if (sub[setting] === null) {
        sub[setting] =
            user_settings[settings_config.generalize_stream_notification_setting[setting]];
    }
    stream_settings_api.set_stream_property(
        sub,
        {property: setting, value: e.target.checked},
        $status_element,
    );
}

export function set_up(settings_panel) {
    const $container = $(settings_panel.container);
    const settings_object = settings_panel.settings_object;
    const $notification_sound_elem = $(settings_panel.notification_sound_elem);
    const for_realm_settings = settings_panel.for_realm_settings;
    const $notification_sound_dropdown = $container.find(".setting_notification_sound");

    $container.find(".play_notification_sound").on("click", () => {
        if ($notification_sound_dropdown.val().toLowerCase() !== "none") {
            ui_util.play_audio($notification_sound_elem[0]);
        }
    });

    update_desktop_icon_count_display(settings_panel);

    $notification_sound_dropdown.val(settings_object.notification_sound);

    $container.find(".enable_sounds, .enable_stream_audible_notifications").on("change", () => {
        if (
            $container.find(".enable_stream_audible_notifications").prop("checked") ||
            $container.find(".enable_sounds").prop("checked")
        ) {
            $notification_sound_dropdown.prop("disabled", false);
            $notification_sound_dropdown.parent().removeClass("control-label-disabled");
        } else {
            $notification_sound_dropdown.prop("disabled", true);
            $notification_sound_dropdown.parent().addClass("control-label-disabled");
        }
    });

    set_notification_batching_ui(
        $container,
        settings_object.email_notifications_batching_period_seconds,
    );

    const $realm_name_in_email_notifications_policy_dropdown = $container.find(
        ".setting_realm_name_in_email_notifications_policy",
    );
    $realm_name_in_email_notifications_policy_dropdown.val(
        settings_object.realm_name_in_email_notifications_policy,
    );

    const $automatically_follow_topics_policy_dropdown = $container.find(
        ".setting_automatically_follow_topics_policy",
    );
    $automatically_follow_topics_policy_dropdown.val(
        settings_object.automatically_follow_topics_policy,
    );

    const $automatically_unmute_topics_in_muted_streams_policy_dropdown = $container.find(
        ".setting_automatically_unmute_topics_in_muted_streams_policy",
    );
    $automatically_unmute_topics_in_muted_streams_policy_dropdown.val(
        settings_object.automatically_unmute_topics_in_muted_streams_policy,
    );

    set_enable_digest_emails_visibility($container, for_realm_settings);

    if (for_realm_settings) {
        // For the realm-level defaults page, we use the common
        // settings_org.js handlers, so we can return early here.
        return;
    }

    // Common handler for sending requests to the server when an input
    // element is changed.
    $container.find(".notification-settings-form").on("change", "input, select", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const $input_elem = $(e.currentTarget);
        if ($input_elem.parents("#stream-specific-notify-table").length) {
            stream_notification_setting_changed(e);
            return;
        }
        let setting_name = $input_elem.attr("name");
        let setting_value = settings_components.get_input_element_value(this);

        if (setting_name === "email_notifications_batching_period_seconds") {
            if ($input_elem.val() === "custom_period") {
                set_notification_batching_ui(
                    $container,
                    settings_object.email_notifications_batching_period_seconds,
                    true,
                );
                return;
            }
            set_notification_batching_ui($container, setting_value);
        } else if (setting_name === "email_notification_batching_period_edit_minutes") {
            // This field is in minutes, but the actual setting is seconds
            setting_value = setting_value * 60;
            set_notification_batching_ui($container, setting_value);
            setting_name = "email_notifications_batching_period_seconds";
        }

        if (
            settings_config.pm_mention_notification_settings.includes(setting_name) &&
            !setting_value
        ) {
            let enabled_pm_mention_notifications_count = 0;
            const pm_mention_notification_settings =
                settings_config.get_notifications_table_row_data(
                    settings_config.pm_mention_notification_settings,
                    user_settings,
                );

            for (const setting of pm_mention_notification_settings) {
                if (setting.is_checked && !setting.is_disabled) {
                    enabled_pm_mention_notifications_count += 1;
                }
            }
            if (enabled_pm_mention_notifications_count === 1) {
                const html_body = render_confirm_disable_all_notifications();
                $input_elem.prop("checked", user_settings[setting_name]);

                confirm_dialog.launch({
                    html_heading: $t_html({defaultMessage: "Disable notifications?"}),
                    html_body,
                    on_click: () =>
                        change_notification_setting(
                            setting_name,
                            setting_value,
                            $input_elem.closest(".subsection-parent").find(".alert-notification"),
                        ),
                });
                return;
            }
        }

        change_notification_setting(
            setting_name,
            setting_value,
            $input_elem.closest(".subsection-parent").find(".alert-notification"),
        );
    });

    // This final patch of settings are ones for which we
    // intentionally don't let organization administrators set
    // organization-level defaults.
    $container.find(".send_test_notification").on("click", () => {
        message_notifications.send_test_notification(
            $t({defaultMessage: "This is what a Zulip notification looks like."}),
        );
    });

    set_enable_marketing_emails_visibility();
    rerender_ui();
}

export function update_page(settings_panel) {
    const $container = $(settings_panel.container);
    const settings_object = settings_panel.settings_object;
    for (const setting of settings_config.all_notification_settings) {
        switch (setting) {
            case "enable_offline_push_notifications": {
                if (!realm.realm_push_notifications_enabled) {
                    // If push notifications are disabled at the realm level,
                    // we should just leave the checkbox always off.
                    break;
                }
                $container
                    .find(`.${CSS.escape(setting)}`)
                    .prop("checked", settings_object[setting]);
                break;
            }
            case "desktop_icon_count_display": {
                update_desktop_icon_count_display(settings_panel);
                break;
            }
            case "email_notifications_batching_period_seconds": {
                set_notification_batching_ui($container, settings_object[setting]);
                break;
            }
            case "notification_sound":
            case "realm_name_in_email_notifications_policy":
            case "automatically_follow_topics_policy":
            case "automatically_unmute_topics_in_muted_streams_policy": {
                $container.find(`.setting_${CSS.escape(setting)}`).val(settings_object[setting]);
                break;
            }
            default: {
                $container
                    .find(`.${CSS.escape(setting)}`)
                    .prop("checked", settings_object[setting]);
                break;
            }
        }
    }
    rerender_ui();
}

export function update_muted_stream_state(sub) {
    const $row = $(
        `#stream-specific-notify-table .stream-notifications-row[data-stream-id='${CSS.escape(
            sub.stream_id,
        )}']`,
    );

    if (sub.is_muted) {
        $row.find(".unmute_stream").show();
    } else {
        $row.find(".unmute_stream").hide();
    }
    $row.find('[name="push_notifications"]').prop(
        "disabled",
        !realm.realm_push_notifications_enabled,
    );
}

export function initialize() {
    user_settings_panel.container = "#user-notification-settings";
    user_settings_panel.settings_object = user_settings;
    user_settings_panel.notification_sound_elem = "#user-notification-sound-audio";
    user_settings_panel.for_realm_settings = false;

    // Set up click handler for unmuting streams via this UI.
    $("body").on("click", "#stream-specific-notify-table .unmute_stream", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const $row = $(e.currentTarget).closest(".stream-notifications-row");
        const stream_id = Number.parseInt($row.attr("data-stream-id"), 10);
        const sub = sub_store.get(stream_id);

        stream_settings_api.set_stream_property(
            sub,
            {property: "is_muted", value: !sub.is_muted},
            $row.closest(".subsection-parent").find(".alert-notification"),
        );
    });
}
