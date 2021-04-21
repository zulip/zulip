import Handlebars from "handlebars/runtime";
import $ from "jquery";

import timezones from "../generated/timezones.json";
import render_settings_tab from "../templates/settings_tab.hbs";

import * as admin from "./admin";
import * as blueslip from "./blueslip";
import * as common from "./common";
import {$t, $t_html} from "./i18n";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as people from "./people";
import * as settings_bots from "./settings_bots";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import * as settings_panel_menu from "./settings_panel_menu";
import * as settings_sections from "./settings_sections";
import * as settings_toggle from "./settings_toggle";

export let settings_label;

$("body").ready(() => {
    $("#settings_overlay_container").on("click", (e) => {
        if (!overlays.is_modal_open()) {
            return;
        }
        if ($(e.target).closest(".modal").length > 0) {
            return;
        }
        e.preventDefault();
        e.stopPropagation();
        // Whenever opening a modal(over settings overlay) in an event handler
        // attached to a click event, make sure to stop the propagation of the
        // event to the parent container otherwise the modal will not open. This
        // is so because this event handler will get fired on any click in settings
        // overlay and subsequently close any open modal.
        overlays.close_active_modal();
    });
});

function setup_settings_label() {
    settings_label = {
        // settings_notification
        enable_online_push_notifications: $t({
            defaultMessage: "Send mobile notifications even if I'm online (useful for testing)",
        }),
        pm_content_in_desktop_notifications: $t({
            defaultMessage: "Include content of private messages in desktop notifications",
        }),
        desktop_icon_count_display: $t({
            defaultMessage: "Unread count summary (appears in desktop sidebar and browser tab)",
        }),
        enable_digest_emails: $t({defaultMessage: "Send digest emails when I'm away"}),
        enable_login_emails: $t({
            defaultMessage: "Send email notifications for new logins to my account",
        }),
        enable_marketing_emails: $t({
            defaultMessage: "Send me occasional marketing emails about Zulip (a few times a year)",
        }),
        message_content_in_email_notifications: $t({
            defaultMessage: "Include message content in message notification emails",
        }),
        realm_name_in_notifications: $t({
            defaultMessage: "Include organization name in subject of message notification emails",
        }),
        presence_enabled: $t({
            defaultMessage: "Display my availability to other users when online",
        }),

        // display settings
        dense_mode: $t({defaultMessage: "Dense mode"}),
        fluid_layout_width: $t({defaultMessage: "Use full width on wide screens"}),
        high_contrast_mode: $t({defaultMessage: "High contrast mode"}),
        left_side_userlist: $t({
            defaultMessage: "Show user list on left sidebar in narrow windows",
        }),
        starred_message_counts: $t({defaultMessage: "Show counts for starred messages"}),
        twenty_four_hour_time: $t({defaultMessage: "Time format"}),
        timezone_auto_update: $t({
            defaultMessage: "Automatically offer to update with my computer’s time zone",
        }),
        translate_emoticons: new Handlebars.SafeString(
            $t_html({
                defaultMessage: "Convert emoticons before sending (<code>:)</code> becomes 😃)",
            }),
        ),
    };
}

export function build_page() {
    setup_settings_label();

    const rendered_settings_tab = render_settings_tab({
        full_name: people.my_full_name(),
        page_params,
        enable_sound_select:
            page_params.enable_sounds || page_params.enable_stream_audible_notifications,
        zuliprc: "zuliprc",
        botserverrc: "botserverrc",
        timezones: timezones.timezones,
        can_create_new_bots: settings_bots.can_create_new_bots(),
        settings_label,
        demote_inactive_streams_values: settings_config.demote_inactive_streams_values,
        color_scheme_values: settings_config.color_scheme_values,
        default_view_values: settings_config.default_view_values,
        twenty_four_hour_time_values: settings_config.twenty_four_hour_time_values,
        general_settings: settings_config.all_notifications().general_settings,
        notification_settings: settings_config.all_notifications().settings,
        desktop_icon_count_display_values: settings_config.desktop_icon_count_display_values,
        show_push_notifications_tooltip: settings_config.all_notifications()
            .show_push_notifications_tooltip,
        display_settings: settings_config.get_all_display_settings(),
        user_can_change_name: settings_data.user_can_change_name(),
        user_can_change_avatar: settings_data.user_can_change_avatar(),
        user_role_text: people.get_user_type(page_params.user_id),
    });

    $(".settings-box").html(rendered_settings_tab);
    common.setup_password_visibility_toggle(
        "#old_password",
        "#old_password + .password_visibility_toggle",
        {tippy_tooltips: true},
    );
    common.setup_password_visibility_toggle(
        "#new_password",
        "#new_password + .password_visibility_toggle",
        {tippy_tooltips: true},
    );
}

export function launch(section) {
    build_page();
    admin.build_page();
    settings_sections.reset_sections();

    overlays.open_settings();
    settings_panel_menu.normal_settings.activate_section_or_default(section);
    settings_toggle.highlight_toggle("settings");
}

export function set_settings_header(key) {
    const header_text = $(
        `#settings_page .sidebar-list [data-section='${CSS.escape(key)}'] .text`,
    ).text();
    if (header_text) {
        $(".settings-header h1 .section").text(" / " + header_text);
    } else {
        blueslip.warn(
            "Error: the key '" +
                key +
                "' does not exist in the settings" +
                " sidebar list. Please add it.",
        );
    }
}
