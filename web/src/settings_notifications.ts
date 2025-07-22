import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";
import * as z from "zod/mini";

import render_confirm_disable_all_notifications from "../templates/confirm_dialog/confirm_disable_all_notifications.hbs";
import render_confirm_reset_stream_notifications from "../templates/confirm_dialog/confirm_reset_stream_notifications.hbs";
import render_stream_specific_notification_row from "../templates/settings/stream_specific_notification_row.hbs";

import * as banners from "./banners.ts";
import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import * as message_notifications from "./message_notifications.ts";
import {page_params} from "./page_params.ts";
import * as settings_components from "./settings_components.ts";
import * as settings_config from "./settings_config.ts";
import type {SettingsPanel} from "./settings_preferences.ts";
import * as settings_ui from "./settings_ui.ts";
import {realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_settings_api from "./stream_settings_api.ts";
import type {SubData} from "./stream_settings_api.ts";
import * as stream_settings_data from "./stream_settings_data.ts";
import {stream_specific_notification_settings_schema} from "./stream_types.ts";
import * as sub_store from "./sub_store.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as ui_util from "./ui_util.ts";
import * as unread_ui from "./unread_ui.ts";
import {
    pm_notification_settings_schema,
    user_settings,
    user_settings_schema,
} from "./user_settings.ts";
import * as util from "./util.ts";

export let user_settings_panel: SettingsPanel | undefined;
let customize_stream_notifications_widget: dropdown_widget.DropdownWidget;
const stream_ids_with_custom_notifications = new Set<number>();

const DESKTOP_NOTIFICATIONS_BANNER: banners.Banner = {
    intent: "warning",
    label: $t({
        defaultMessage: "Zulip needs your permission to enable desktop notifications.",
    }),
    buttons: [
        {
            label: $t({defaultMessage: "Enable notifications"}),
            custom_classes: "desktop-notifications-request",
            attention: "primary",
        },
    ],
    close_button: true,
    custom_classes: "desktop-setting-notifications",
};

function rerender_ui(): void {
    const $unmatched_streams_table = $("#stream-specific-notify-table");
    if ($unmatched_streams_table.length === 0) {
        // If we haven't rendered "notification settings" yet, do nothing.
        return;
    }

    const unmatched_streams =
        stream_settings_data.get_unmatched_streams_for_notification_settings();

    $unmatched_streams_table.find(".stream-notifications-row").remove();

    const muted_stream_ids = stream_data.muted_stream_ids();
    stream_ids_with_custom_notifications.clear();

    for (const stream of unmatched_streams) {
        $unmatched_streams_table.append(
            $(
                render_stream_specific_notification_row({
                    stream,
                    stream_specific_notification_settings:
                        settings_config.stream_specific_notification_settings,
                    is_disabled:
                        settings_config.all_notifications(user_settings)
                            .disabled_notification_settings,
                    muted: muted_stream_ids.includes(stream.stream_id),
                    push_notifications_disabled: !realm.realm_push_notifications_enabled,
                }),
            ),
        );
        stream_ids_with_custom_notifications.add(stream.stream_id);
    }

    if (unmatched_streams.length === 0) {
        $unmatched_streams_table.css("display", "none");
        $("#customize_stream_notifications_widget .dropdown_widget_value").text(
            $t({defaultMessage: "Customize a channel"}),
        );
    } else {
        $unmatched_streams_table.css("display", "table-row-group");
        $("#customize_stream_notifications_widget .dropdown_widget_value").text(
            $t({defaultMessage: "Customize another channel"}),
        );
    }
    update_desktop_notification_banner();
}

function update_desktop_notification_banner(): void {
    // As is also noted in `navbar_alerts.ts`, notifications *basically*
    // don't work on any mobile platforms, so don't event show the banners.
    // This prevents trying to access things that don't exist, like
    // `Notification.permission` in a mobile context, in which we'll also
    // hide the ability to send a test notification before exiting with an
    // early return.
    if (util.is_mobile()) {
        $(".send_test_notification").hide();
        return;
    }
    const permission = Notification.permission;
    const $banner_container = $(".desktop-notification-settings-banners");
    if (permission === "granted") {
        banners.close($(".desktop-notification-settings-banners .desktop-setting-notifications"));
        $(".send_test_notification").show();
    } else {
        if ($banner_container.find(".desktop-setting-notifications").length === 0) {
            banners.append(DESKTOP_NOTIFICATIONS_BANNER, $banner_container);
        }
        $(".send_test_notification").hide();
    }
}

function change_notification_setting(
    setting: string,
    value: number | string | boolean,
    $status_element: JQuery,
): void {
    const data = {
        [setting]: value,
    };
    settings_ui.do_settings_change(channel.patch, "/json/settings", data, $status_element);
}

function update_desktop_icon_count_display(settings_panel: SettingsPanel): void {
    const $container = $(settings_panel.container);
    const settings_object = settings_panel.settings_object;
    $container
        .find(".setting_desktop_icon_count_display")
        .val(settings_object.desktop_icon_count_display);
    if (!settings_panel.for_realm_settings) {
        unread_ui.update_unread_counts();
    }
}

export function set_notification_batching_ui(
    $container: JQuery,
    setting_seconds: number,
    force_custom = false,
): void {
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
        $edit_elem.attr("id")!,
        show_edit_elem,
    );
}

export function set_enable_digest_emails_visibility(
    $container: JQuery,
    for_realm_settings: boolean,
): void {
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

export function set_enable_marketing_emails_visibility(): void {
    const $container = $("#user-notification-settings");
    if (page_params.corporate_enabled) {
        $container.find(".enable_marketing_emails_label").parent().show();
    } else {
        $container.find(".enable_marketing_emails_label").parent().hide();
    }
}

function stream_notification_setting_changed(target: HTMLInputElement, stream_id: number): void {
    if (!stream_id) {
        blueslip.error("Cannot find stream id for target");
        return;
    }

    const sub = sub_store.get(stream_id);
    if (!sub) {
        blueslip.error("stream_notification_setting_changed() failed id lookup", {stream_id});
        return;
    }

    const $status_element = $(target).closest(".subsection-parent").find(".alert-notification");
    const setting = z.keyof(stream_specific_notification_settings_schema).parse(target.name);
    sub[setting] ??= user_settings[settings_config.generalize_stream_notification_setting[setting]];
    stream_settings_api.set_stream_property(
        sub,
        {property: setting, value: target.checked},
        $status_element,
    );
}

function change_state_of_customize_stream_notifications_widget(
    event: JQuery.ClickEvent,
    dropdown: tippy.Instance,
): void {
    dropdown.hide();
    event.preventDefault();
    event.stopPropagation();

    assert(customize_stream_notifications_widget !== undefined);
    customize_stream_notifications_widget.render();
    const stream_id = customize_stream_notifications_widget.value();
    assert(typeof stream_id === "number");

    const $customizable_stream_notifications_table = $("#customizable_stream_notifications_table");
    $customizable_stream_notifications_table.find("input[type='checkbox']").prop("disabled", false);

    if (!realm.realm_push_notifications_enabled) {
        $customizable_stream_notifications_table
            .find("input.push_notifications")
            .prop("disabled", true);
    }

    for (const notification_setting of settings_config.stream_specific_notification_settings) {
        const checked_state = stream_data.receives_notifications(stream_id, notification_setting);
        $customizable_stream_notifications_table
            .find(`.${CSS.escape(notification_setting)}`)
            .prop("checked", checked_state);
    }
}

function get_streams_to_customize_notifications(): dropdown_widget.Option[] {
    return stream_data
        .get_options_for_dropdown_widget()
        .filter(({stream}) => !stream_ids_with_custom_notifications.has(stream.stream_id));
}

function render_customize_stream_notifications_widget(): void {
    customize_stream_notifications_widget = new dropdown_widget.DropdownWidget({
        widget_name: "customize_stream_notifications",
        get_options: get_streams_to_customize_notifications,
        item_click_callback: change_state_of_customize_stream_notifications_widget,
        $events_container: $("#user-notification-settings .notification-settings-form"),
        unique_id_type: "number",
    });
    customize_stream_notifications_widget.setup();
}

export function do_reset_stream_notifications(elem: HTMLElement, sub: StreamSubscription): void {
    const data: SubData = [{stream_id: sub.stream_id, property: "is_muted", value: false}];
    for (const [per_stream_setting_name, global_setting_name] of Object.entries(
        settings_config.generalize_stream_notification_setting,
    )) {
        data.push({
            stream_id: sub.stream_id,
            property: z
                .keyof(stream_specific_notification_settings_schema)
                .parse(per_stream_setting_name),
            value: user_settings[global_setting_name],
        });
    }

    stream_settings_api.bulk_set_stream_property(
        data,
        $(elem).closest(".subsection-parent").find(".alert-notification"),
    );
}

function reset_stream_notifications(elem: HTMLElement): void {
    const $row = $(elem).closest(".stream-notifications-row");
    const stream_id = Number.parseInt($row.attr("data-stream-id")!, 10);
    const sub = sub_store.get(stream_id);
    assert(sub !== undefined);

    const html_body = render_confirm_reset_stream_notifications({sub});

    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Reset to default notifications?"}),
        html_body,
        id: "confirm_reset_stream_notifications_modal",
        on_click() {
            do_reset_stream_notifications(elem, sub);
        },
    });
}

export function set_up(settings_panel: SettingsPanel): void {
    const $container = $(settings_panel.container);
    const settings_object = settings_panel.settings_object;
    assert(settings_panel.notification_sound_elem !== null);
    const $notification_sound_elem = $<HTMLAudioElement>(settings_panel.notification_sound_elem);
    const for_realm_settings = settings_panel.for_realm_settings;
    const $notification_sound_dropdown = $container.find<HTMLSelectElement & {type: "select-one"}>(
        "select:not([multiple]).setting_notification_sound",
    );

    $container.find(".play_notification_sound").on("click", () => {
        if ($notification_sound_dropdown.val()!.toLowerCase() !== "none") {
            void ui_util.play_audio(util.the($notification_sound_elem));
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

    $container
        .find(".setting_resolved_topic_notice_auto_read_policy")
        .val(settings_object.resolved_topic_notice_auto_read_policy);

    const $automatically_unmute_topics_in_muted_streams_policy_dropdown = $container.find(
        ".setting_automatically_unmute_topics_in_muted_streams_policy",
    );
    $automatically_unmute_topics_in_muted_streams_policy_dropdown.val(
        settings_object.automatically_unmute_topics_in_muted_streams_policy,
    );

    update_desktop_notification_banner();

    $container.on("click", ".desktop-notifications-request", (e) => {
        e.preventDefault();
        // This is only accessed via the notifications banner, so we
        // do not need to do a mobile check here--as that banner is
        // not shown in a mobile context anyway.
        void Notification.requestPermission().then((permission) => {
            if (permission === "granted") {
                update_desktop_notification_banner();
            } else if (permission === "denied") {
                window.open(
                    "/help/desktop-notifications#check-platform-settings",
                    "_blank",
                    "noopener noreferrer",
                );
            }
        });
    });

    set_enable_digest_emails_visibility($container, for_realm_settings);

    if (for_realm_settings) {
        // For the realm-level defaults page, we use the common
        // settings_org.ts handlers, so we can return early here.
        return;
    }

    // Common handler for sending requests to the server when an input
    // element is changed.
    const $notification_settings_form = $container.find(".notification-settings-form");
    $notification_settings_form.on("change", "input, select", function (this: HTMLElement, e) {
        e.preventDefault();
        e.stopPropagation();
        const $input_elem = $(e.currentTarget);
        if ($input_elem.parents("#stream-specific-notify-table").length > 0) {
            const $row = $input_elem.closest(".stream-notifications-row");
            const stream_id = Number.parseInt($row.attr("data-stream-id")!, 10);
            assert(e.currentTarget instanceof HTMLInputElement);
            stream_notification_setting_changed(e.currentTarget, stream_id);
            return;
        }
        if ($input_elem.parents("#customizable_stream_notifications_table").length > 0) {
            assert(e.currentTarget instanceof HTMLInputElement);
            assert(customize_stream_notifications_widget !== undefined);
            const stream_id = customize_stream_notifications_widget.value();
            assert(typeof stream_id === "number");
            stream_notification_setting_changed(e.currentTarget, stream_id);
            return;
        }

        if ($input_elem.attr("data-setting-widget-type") === "time-limit") {
            // For time-limit settings we should always pass the select element
            // to get_input_element_value and not the custom input element.
            const select_elem = util.the(
                $input_elem.closest(".time-limit-setting").find("select.settings_select"),
            );
            const setting_value = settings_components.get_input_element_value(select_elem);
            assert(typeof setting_value === "number");

            // Currently only notification batching setting is the time-limit
            // settings on this page.
            if (
                $input_elem.attr("name") === "email_notifications_batching_period_seconds" &&
                $input_elem.val() === "custom_period"
            ) {
                set_notification_batching_ui(
                    $container,
                    settings_object.email_notifications_batching_period_seconds,
                    true,
                );
                return;
            }
            set_notification_batching_ui($container, setting_value);
            change_notification_setting(
                "email_notifications_batching_period_seconds",
                setting_value,
                $input_elem.closest(".subsection-parent").find(".alert-notification"),
            );
            return;
        }

        const setting_name = z.keyof(user_settings_schema).parse($input_elem.attr("name"));
        // This filters out the GroupSettingValue
        const setting_value = z
            .union([z.string(), z.number(), z.boolean()])
            .parse(settings_components.get_input_element_value(this));

        if (
            z.keyof(pm_notification_settings_schema).safeParse(setting_name).success &&
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
                    on_click() {
                        change_notification_setting(
                            setting_name,
                            setting_value,
                            $input_elem.closest(".subsection-parent").find(".alert-notification"),
                        );
                    },
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
            $t({defaultMessage: "This is a test notification from Zulip."}),
        );
    });

    $("#settings_content").on("click", ".banner-close-button", (e) => {
        e.preventDefault();
        $(".banner-wrapper").remove();
    });

    set_enable_marketing_emails_visibility();
    render_customize_stream_notifications_widget();
    rerender_ui();
}

export function update_page(settings_panel: SettingsPanel): void {
    assert(!settings_panel.for_realm_settings);

    const $container = $(settings_panel.container);
    const settings_object = settings_panel.settings_object;
    for (const untyped_setting of settings_config.all_notification_settings) {
        const setting = z.keyof(user_settings_schema).parse(untyped_setting);
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
    $container
        .find("#customizable_stream_notifications_table input[type='checkbox']")
        .each(function () {
            $(this).prop("disabled", true).prop("checked", false);
        });

    rerender_ui();
}

export function update_muted_stream_state(sub: StreamSubscription): void {
    const $row = $(
        `#stream-specific-notify-table .stream-notifications-row[data-stream-id='${CSS.escape(
            sub.stream_id.toString(),
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

export function initialize(): void {
    user_settings_panel = {
        container: "#user-notification-settings",
        settings_object: user_settings,
        notification_sound_elem: "audio#user-notification-sound-audio",
        for_realm_settings: false,
    };

    // Set up click handler for unmuting streams via this UI.
    $("body").on("click", "#stream-specific-notify-table .unmute_stream", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const $row = $(e.currentTarget).closest(".stream-notifications-row");
        const stream_id = Number.parseInt($row.attr("data-stream-id")!, 10);
        const sub = sub_store.get(stream_id);
        assert(sub !== undefined);

        stream_settings_api.set_stream_property(
            sub,
            {property: "is_muted", value: !sub.is_muted},
            $row.closest(".subsection-parent").find(".alert-notification"),
        );
    });

    $("body").on(
        "click",
        "#stream-specific-notify-table .reset_stream_notifications",
        function on_click(this: HTMLElement) {
            reset_stream_notifications(this);
        },
    );
}
