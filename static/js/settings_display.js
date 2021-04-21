import $ from "jquery";

import * as channel from "./channel";
import * as emojisets from "./emojisets";
import {$t_html} from "./i18n";
import * as loading from "./loading";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as settings_config from "./settings_config";
import * as settings_ui from "./settings_ui";
import * as ui_report from "./ui_report";

const meta = {
    loaded: false,
};

function change_display_setting(data, status_element, success_msg_html, sticky) {
    const $status_el = $(status_element);
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
    settings_ui.do_settings_change(
        channel.patch,
        "/json/settings/display",
        data,
        status_element,
        opts,
    );
}

export function set_up() {
    meta.loaded = true;
    $("#display-settings-status").hide();

    $("#user_timezone").val(page_params.timezone);

    $("#demote_inactive_streams").val(page_params.demote_inactive_streams);

    $("#color_scheme").val(page_params.color_scheme);

    $("#default_view").val(page_params.default_view);

    $("#twenty_four_hour_time").val(JSON.stringify(page_params.twenty_four_hour_time));

    $("#timezone_auto_update").prop("checked", page_params.timezone_auto_update);

    $(`.emojiset_choice[value="${CSS.escape(page_params.emojiset)}"]`).prop("checked", true);

    $("#default_language_modal [data-dismiss]").on("click", () => {
        overlays.close_modal("#default_language_modal");
    });

    const all_display_settings = settings_config.get_all_display_settings();
    for (const setting of all_display_settings.settings.user_display_settings) {
        $(`#${CSS.escape(setting)}`).on("change", function () {
            const data = {};
            data[setting] = JSON.stringify($(this).prop("checked"));

            if (["left_side_userlist"].includes(setting)) {
                change_display_setting(
                    data,
                    "#display-settings-status",
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
                change_display_setting(data, "#display-settings-status");
            }
        });
    }

    $("#default_language_modal .language").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        overlays.close_modal("#default_language_modal");

        const $link = $(e.target).closest("a[data-code]");
        const setting_value = $link.attr("data-code");
        const data = {default_language: JSON.stringify(setting_value)};

        const new_language = $link.attr("data-name");
        $("#default_language_name").text(new_language);

        change_display_setting(
            data,
            "#language-settings-status",
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

    $("#default_language").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        overlays.open_modal("#default_language_modal");
    });

    $("#demote_inactive_streams").on("change", function () {
        const data = {demote_inactive_streams: this.value};
        change_display_setting(data, "#display-settings-status");
    });

    $("#color_scheme").on("change", function () {
        const data = {color_scheme: this.value};
        change_display_setting(data, "#display-settings-status");
    });

    $("#default_view").on("change", function () {
        const data = {default_view: JSON.stringify(this.value)};
        change_display_setting(data, "#display-settings-status");
    });

    $("body").on("click", ".reload_link", () => {
        window.location.reload();
    });

    $("#twenty_four_hour_time").on("change", function () {
        const data = {twenty_four_hour_time: this.value};
        change_display_setting(data, "#time-settings-status");
    });

    $("#user_timezone").on("change", function () {
        const data = {timezone: JSON.stringify(this.value)};
        change_display_setting(data, "#time-settings-status");
    });

    $("#timezone_auto_update").on("change", function () {
        const data = {timezone_auto_update: $(this).prop("checked")};
        change_display_setting(data, "#time-settings-status");
    });

    $(".emojiset_choice").on("click", function () {
        const data = {emojiset: JSON.stringify($(this).val())};
        const current_emojiset = JSON.stringify(page_params.emojiset);
        if (current_emojiset === data.emojiset) {
            return;
        }
        const spinner = $("#emoji-settings-status").expectOne();
        loading.make_indicator(spinner, {text: settings_ui.strings.saving});

        channel.patch({
            url: "/json/settings/display",
            data,
            success() {},
            error(xhr) {
                ui_report.error(
                    settings_ui.strings.failure_html,
                    xhr,
                    $("#emoji-settings-status").expectOne(),
                );
            },
        });
    });

    $("#translate_emoticons").on("change", function () {
        const data = {translate_emoticons: JSON.stringify(this.checked)};
        change_display_setting(data, "#emoji-settings-status");
    });
}

export async function report_emojiset_change() {
    // TODO: Clean up how this works so we can use
    // change_display_setting.  The challenge is that we don't want to
    // report success before the server_events request returns that
    // causes the actual sprite sheet to change.  The current
    // implementation is wrong, though, in that it displays the UI
    // update in all active browser windows.

    await emojisets.select(page_params.emojiset);

    if ($("#emoji-settings-status").length) {
        loading.destroy_indicator($("#emojiset_spinner"));
        $("#emojiset_select").val(page_params.emojiset);
        ui_report.success(
            $t_html({defaultMessage: "Emojiset changed successfully!"}),
            $("#emoji-settings-status").expectOne(),
        );
        const spinner = $("#emoji-settings-status").expectOne();
        settings_ui.display_checkmark(spinner);
    }
}

export function update_page() {
    $("#left_side_userlist").prop("checked", page_params.left_side_userlist);
    $("#default_language_name").text(page_params.default_language_name);
    $("#translate_emoticons").prop("checked", page_params.translate_emoticons);
    $("#twenty_four_hour_time").val(JSON.stringify(page_params.twenty_four_hour_time));
    $("#timezone_auto_update").prop("checked", page_params.timezone_auto_update);
    $("#color_scheme").val(JSON.stringify(page_params.color_scheme));
    $("#default_view").val(page_params.default_view);

    // TODO: Set emojiset selector here.
    // Longer term, we'll want to automate this function
}
