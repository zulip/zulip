import {parseISO} from "date-fns";
import $ from "jquery";

import timezones from "../generated/timezones.json";
import render_settings_overlay from "../templates/settings_overlay.hbs";
import render_settings_tab from "../templates/settings_tab.hbs";

import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as flatpickr from "./flatpickr";
import {$t, $t_html} from "./i18n";
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
import * as timerender from "./timerender";
import {user_settings} from "./user_settings";

export let settings_label;

$(() => {
    $("#settings_overlay_container").on("click", (e) => {
        if (!overlays.is_modal_open()) {
            return;
        }
        if ($(e.target).closest(".micromodal").length > 0) {
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
            defaultMessage: "Display my availability to other users",
        }),
        presence_enabled_parens_text: $t({defaultMessage: "invisible mode off"}),
        send_stream_typing_notifications: $t({
            defaultMessage: "Let subscribers see when I'm typing messages in streams",
        }),
        send_private_typing_notifications: $t({
            defaultMessage: "Let recipients see when I'm typing direct messages",
        }),
        send_read_receipts: $t({
            defaultMessage: "Let others see when I've read messages",
        }),

        ...settings_config.notification_settings_labels,
        ...settings_config.display_settings_labels,
    };
}

function get_parsed_date_of_joining() {
    const user_date_joined = people.get_by_user_id(page_params.user_id, false).date_joined;
    return timerender.get_localized_date_or_time_for_format(
        parseISO(user_date_joined),
        "dayofyear_year",
    );
}

function user_can_change_password() {
    if (settings_data.user_email_not_configured()) {
        return false;
    }
    return page_params.realm_email_auth_enabled;
}

export function build_page() {
    setup_settings_label();

    const rendered_settings_tab = render_settings_tab({
        full_name: people.my_full_name(),
        date_joined_text: get_parsed_date_of_joining(),
        page_params,
        development: page_params.development_environment,
        enable_sound_select:
            user_settings.enable_sounds || user_settings.enable_stream_audible_notifications,
        zuliprc: "zuliprc",
        botserverrc: "botserverrc",
        timezones: timezones.timezones,
        can_create_new_bots: settings_bots.can_create_new_bots(),
        settings_label,
        demote_inactive_streams_values: settings_config.demote_inactive_streams_values,
        web_mark_read_on_scroll_policy_values:
            settings_config.web_mark_read_on_scroll_policy_values,
        user_list_style_values: settings_config.user_list_style_values,
        web_stream_unreads_count_display_policy_values:
            settings_config.web_stream_unreads_count_display_policy_values,
        color_scheme_values: settings_config.color_scheme_values,
        default_view_values: settings_config.default_view_values,
        twenty_four_hour_time_values: settings_config.twenty_four_hour_time_values,
        general_settings: settings_config.all_notifications(user_settings).general_settings,
        notification_settings: settings_config.all_notifications(user_settings).settings,
        email_notifications_batching_period_values:
            settings_config.email_notifications_batching_period_values,
        realm_name_in_email_notifications_policy_values:
            settings_config.realm_name_in_email_notifications_policy_values,
        desktop_icon_count_display_values: settings_config.desktop_icon_count_display_values,
        show_push_notifications_tooltip:
            settings_config.all_notifications(user_settings).show_push_notifications_tooltip,
        display_settings: settings_config.get_all_display_settings(),
        user_can_change_name: settings_data.user_can_change_name(),
        user_can_change_avatar: settings_data.user_can_change_avatar(),
        user_can_change_email: settings_data.user_can_change_email(),
        user_role_text: people.get_user_type(page_params.user_id),
        default_language_name: settings_display.user_default_language_name,
        default_language: user_settings.default_language,
        realm_push_notifications_enabled: page_params.realm_push_notifications_enabled,
        settings_object: user_settings,
        send_read_receipts_tooltip: $t({
            defaultMessage: "Read receipts are currently disabled in this organization.",
        }),
        user_is_only_organization_owner: people.is_current_user_only_owner(),
        email_address_visibility_values: settings_config.email_address_visibility_values,
        owner_is_only_user_in_organization: people.get_active_human_count() === 1,
        user_can_change_password: user_can_change_password(),
        user_has_email_set: !settings_data.user_email_not_configured(),
    });

    settings_bots.update_bot_settings_tip($("#personal-bot-settings-tip"), false);
    $(".settings-box").html(rendered_settings_tab);
}

export function open_settings_overlay() {
    overlays.open_overlay({
        name: "settings",
        $overlay: $("#settings_overlay_container"),
        on_close() {
            browser_history.exit_overlay();
            flatpickr.close_all();
        },
    });
}

export function launch(section) {
    settings_sections.reset_sections();

    open_settings_overlay();
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
        can_create_new_bots: settings_bots.can_create_new_bots(),
    });
    $("#settings_overlay_container").append(rendered_settings_overlay);
}
