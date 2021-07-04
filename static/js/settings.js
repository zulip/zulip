import {parseISO} from "date-fns";
import $ from "jquery";

import timezones from "../generated/timezones.json";
import render_settings_overlay from "../templates/settings_overlay.hbs";
import render_settings_tab from "../templates/settings_tab.hbs";

import * as admin from "./admin";
import * as blueslip from "./blueslip";
import * as common from "./common";
import {$t, $t_html, get_language_list_columns} from "./i18n";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as people from "./people";
import * as settings_bots from "./settings_bots";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import * as settings_display from "./settings_display";
import * as settings_panel_menu from "./settings_panel_menu";
import * as settings_sections from "./settings_sections";
import * as settings_toggle from "./settings_toggle";
import {user_settings} from "./user_settings";

export let settings_label;

$("body").ready(() => {
    $("#settings_overlay_container").on("click", (e) => {
        if (!overlays.is_modal_open()) {
            return;
        }
        if ($(e.target).closest(".modal, .micromodal").length > 0) {
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
        presence_enabled: $t({
            defaultMessage: "Display my availability to other users when online",
        }),
        send_stream_typing_notifications: $t({
            defaultMessage: "Let subscribers see when I'm typing messages in streams",
        }),
        send_private_typing_notifications: $t({
            defaultMessage: "Let recipients see when I'm typing private messages",
        }),
        send_read_receipts: $t({
            defaultMessage: "Let participants see when I've read messages",
        }),

        ...settings_config.notification_settings_labels,
        ...settings_config.display_settings_labels,
    };
}

function get_parsed_date_of_joining() {
    const user_date_joined = people.get_by_user_id(page_params.user_id, false).date_joined;
    const dateFormat = new Intl.DateTimeFormat("default", {dateStyle: "long"});
    return dateFormat.format(parseISO(user_date_joined));
}

export function build_page() {
    setup_settings_label();

    const rendered_settings_tab = render_settings_tab({
        full_name: people.my_full_name(),
        date_joined_text: get_parsed_date_of_joining(),
        page_params,
        enable_sound_select:
            user_settings.enable_sounds || user_settings.enable_stream_audible_notifications,
        zuliprc: "zuliprc",
        botserverrc: "botserverrc",
        timezones: timezones.timezones,
        can_create_new_bots: settings_bots.can_create_new_bots(),
        settings_label,
        demote_inactive_streams_values: settings_config.demote_inactive_streams_values,
        color_scheme_values: settings_config.color_scheme_values,
        default_view_values: settings_config.default_view_values,
        twenty_four_hour_time_values: settings_config.twenty_four_hour_time_values,
        general_settings: settings_config.all_notifications(user_settings).general_settings,
        notification_settings: settings_config.all_notifications(user_settings).settings,
        email_notifications_batching_period_values:
            settings_config.email_notifications_batching_period_values,
        desktop_icon_count_display_values: settings_config.desktop_icon_count_display_values,
        show_push_notifications_tooltip:
            settings_config.all_notifications(user_settings).show_push_notifications_tooltip,
        display_settings: settings_config.get_all_display_settings(),
        user_can_change_name: settings_data.user_can_change_name(),
        user_can_change_avatar: settings_data.user_can_change_avatar(),
        user_role_text: people.get_user_type(page_params.user_id),
        default_language_name: settings_display.user_default_language_name,
        language_list_dbl_col: get_language_list_columns(user_settings.default_language),
        settings_object: user_settings,
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
    const selected_tab_key = $("#settings_page .tab-switcher .selected").data("tab-key");
    let header_prefix = $t_html({defaultMessage: "Personal settings"});
    if (selected_tab_key === "organization") {
        header_prefix = $t_html({defaultMessage: "Organization settings"});
    }
    $(".settings-header h1 .header-prefix").text(header_prefix);

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

export function initialize() {
    const rendered_settings_overlay = render_settings_overlay({
        is_owner: page_params.is_owner,
        is_admin: page_params.is_admin,
        is_guest: page_params.is_guest,
        show_uploaded_files_section: page_params.max_file_upload_size_mib > 0,
        show_emoji_settings_lock:
            !page_params.is_admin && page_params.realm_add_emoji_by_admins_only,
    });
    $("#settings_overlay_container").append(rendered_settings_overlay);
}
