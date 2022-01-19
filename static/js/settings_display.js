import $ from "jquery";

import render_dialog_default_language from "../templates/default_language_modal.hbs";

import * as channel from "./channel";
import * as dialog_widget from "./dialog_widget";
import * as emojisets from "./emojisets";
import {$t_html, get_language_list_columns, get_language_name} from "./i18n";
import * as loading from "./loading";
import * as overlays from "./overlays";
import * as settings_org from "./settings_org";
import * as settings_ui from "./settings_ui";
import * as ui_report from "./ui_report";
import {user_settings} from "./user_settings";

const meta = {
    loaded: false,
};

export const user_settings_panel = {};

export let user_default_language_name;

export function set_default_language_name(name) {
    user_default_language_name = name;
}

function change_display_setting(data, $status_el, success_msg_html, sticky) {
    const status_is_sticky = $status_el.data("is_sticky");
    const display_message_html = status_is_sticky
        ? $status_el.data("sticky_msg_html")
        : success_msg_html;
    const opts = {
        success_msg_html: display_message_html,
        sticky: status_is_sticky || sticky,
    };

    if (sticky) {
        $status_el.data("is_sticky", true);
        $status_el.data("sticky_msg_html", success_msg_html);
    }
    settings_ui.do_settings_change(channel.patch, "/json/settings", data, $status_el, opts);
}

export function set_up(settings_panel) {
    meta.loaded = true;
    const container = $(settings_panel.container);
    const settings_object = settings_panel.settings_object;
    const for_realm_settings = settings_panel.for_realm_settings;

    container.find(".advanced-settings-status").hide();

    // Select current values for enum/select type fields. For boolean
    // fields, the current value is set automatically in the template.
    container.find(".setting_demote_inactive_streams").val(settings_object.demote_inactive_streams);
    container.find(".setting_color_scheme").val(settings_object.color_scheme);
    container.find(".setting_default_view").val(settings_object.default_view);
    container
        .find(".setting_twenty_four_hour_time")
        .val(JSON.stringify(settings_object.twenty_four_hour_time));
    container
        .find(`.setting_emojiset_choice[value="${CSS.escape(settings_object.emojiset)}"]`)
        .prop("checked", true);

    if (for_realm_settings) {
        // For the realm-level defaults page, we use the common
        // settings_org.js handlers, so we can return early here.
        return;
    }

    // Common handler for sending requests to the server when an input
    // element is changed.
    container.on("change", "input[type=checkbox], select", function (e) {
        const input_elem = $(e.currentTarget);
        const setting = input_elem.attr("name");
        const data = {};
        data[setting] = settings_org.get_input_element_value(this);
        const status_element = input_elem.closest(".subsection-parent").find(".alert-notification");

        if (["left_side_userlist"].includes(setting)) {
            change_display_setting(
                data,
                status_element,
                $t_html(
                    {
                        defaultMessage:
                            "Saved. Please <z-link>reload</z-link> for the change to take effect.",
                    },
                    {"z-link": (content_html) => `<a class='reload_link'>${content_html}</a>`},
                ),
                true,
            );
        } else {
            change_display_setting(data, status_element);
        }
    });

    function default_language_modal_post_render() {
        $("#user_default_language_modal")
            .find(".language")
            .on("click", (e) => {
                e.preventDefault();
                e.stopPropagation();
                dialog_widget.close_modal();

                const $link = $(e.target).closest("a[data-code]");
                const setting_value = $link.attr("data-code");
                const data = {default_language: setting_value};

                const new_language = $link.attr("data-name");
                container.find(".default_language_name").text(new_language);

                change_display_setting(
                    data,
                    container.find(".lang-time-settings-status"),
                    $t_html(
                        {
                            defaultMessage:
                                "Saved. Please <z-link>reload</z-link> for the change to take effect.",
                        },
                        {"z-link": (content_html) => `<a class='reload_link'>${content_html}</a>`},
                    ),
                    true,
                );
            });
    }

    container.find(".setting_default_language").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const html_body = render_dialog_default_language({
            language_list: get_language_list_columns(user_settings.default_language),
        });

        dialog_widget.launch({
            html_heading: $t_html({defaultMessage: "Select default language"}),
            html_body,
            html_submit_button: $t_html({defaultMessage: "Close"}),
            id: "user_default_language_modal",
            close_on_submit: true,
            focus_submit_on_open: true,
            single_footer_button: true,
            post_render: default_language_modal_post_render,
            on_click: () => {},
        });
    });

    $("body").on("click", ".reload_link", () => {
        window.location.reload();
    });

    container.find(".setting_emojiset_choice").on("click", function () {
        const data = {emojiset: $(this).val()};
        const current_emojiset = settings_object.emojiset;
        if (current_emojiset === data.emojiset) {
            return;
        }
        const spinner = container.find(".theme-settings-status").expectOne();
        loading.make_indicator(spinner, {text: settings_ui.strings.saving});

        channel.patch({
            url: "/json/settings",
            data,
            success() {},
            error(xhr) {
                ui_report.error(
                    settings_ui.strings.failure_html,
                    xhr,
                    container.find(".theme-settings-status").expectOne(),
                );
            },
        });
    });
}

export async function report_emojiset_change(settings_panel) {
    // TODO: Clean up how this works so we can use
    // change_display_setting.  The challenge is that we don't want to
    // report success before the server_events request returns that
    // causes the actual sprite sheet to change.  The current
    // implementation is wrong, though, in that it displays the UI
    // update in all active browser windows.
    await emojisets.select(settings_panel.settings_object.emojiset);

    const spinner = $(settings_panel.container).find(".theme-settings-status");
    if (spinner.length) {
        loading.destroy_indicator(spinner);
        ui_report.success(
            $t_html({defaultMessage: "Emoji set changed successfully!"}),
            spinner.expectOne(),
        );
        spinner.expectOne();
        settings_ui.display_checkmark(spinner);
    }
}

export function update_page(property) {
    if (!overlays.settings_open()) {
        return;
    }
    const container = $(user_settings_panel.container);
    let value = user_settings[property];

    // The default_language button text updates to the language
    // name and not the value of the user_settings property.
    if (property === "default_language") {
        container.find(".default_language_name").text(user_default_language_name);
        return;
    }

    // settings_org.set_input_element_value doesn't support radio
    // button widgets like this one.
    if (property === "emojiset") {
        container.find(`input[value=${CSS.escape(value)}]`).prop("checked", true);
        return;
    }

    // The twenty_four_hour_time setting is represented as a boolean
    // in the API, but a dropdown with "true"/"false" as strings in
    // the UI, so we need to convert its format here.
    if (property === "twenty_four_hour_time") {
        value = value.toString();
    }

    const input_elem = container.find(`[name=${CSS.escape(property)}]`);
    settings_org.set_input_element_value(input_elem, value);
}

export function initialize() {
    const user_language_name = get_language_name(user_settings.default_language);
    set_default_language_name(user_language_name);

    user_settings_panel.container = "#user-display-settings";
    user_settings_panel.settings_object = user_settings;
    user_settings_panel.for_realm_settings = false;
}
