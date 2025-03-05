import $ from "jquery";

import * as channel from "./channel.ts";
import * as settings_data from "./settings_data.ts";
import {current_user, realm} from "./state_data.ts";
import * as ui_util from "./ui_util.ts";
import * as upload_widget from "./upload_widget.ts";
import type {UploadFunction} from "./upload_widget.ts";
import {user_settings} from "./user_settings.ts";

export function build_realm_logo_widget(upload_function: UploadFunction, is_night: boolean): void {
    let logo_section_id = "#realm-day-logo-upload-widget";
    let logo_source = realm.realm_logo_source;

    if (is_night) {
        logo_section_id = "#realm-night-logo-upload-widget";
        logo_source = realm.realm_night_logo_source;
    }

    const $delete_button_elem = $(logo_section_id + " .image-delete-button");
    const $file_input_elem = $<HTMLInputElement>(logo_section_id + " .image_file_input");
    const $file_input_error_elem = $(logo_section_id + " .image_file_input_error");
    const $upload_button_elem = $(logo_section_id + " .image_upload_button");

    const get_file_input = function (): JQuery<HTMLInputElement> {
        return $file_input_elem.expectOne();
    };

    if (!current_user.is_admin) {
        return;
    }

    if (logo_source === "D") {
        $delete_button_elem.hide();
    } else {
        $delete_button_elem.show();
    }

    const data = {night: JSON.stringify(is_night)};
    $delete_button_elem.on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        void channel.del({
            url: "/json/realm/logo",
            data,
        });
    });

    upload_widget.build_direct_upload_widget(
        get_file_input,
        $file_input_error_elem.expectOne(),
        $upload_button_elem.expectOne(),
        upload_function,
        realm.max_logo_file_size_mib,
    );
}

function change_logo_delete_button(
    logo_source: string,
    $logo_delete_button: JQuery,
    $file_input: JQuery<HTMLInputElement>,
): void {
    if (logo_source === "U") {
        $logo_delete_button.show();
    } else {
        $logo_delete_button.hide();
        // Need to clear input because of a small edge case
        // where you try to upload the same image you just deleted.
        $file_input.val("");
    }
}

export function render(): void {
    const $file_input = $<HTMLInputElement>("#realm-day-logo-upload-widget input.image_file_input");
    const $night_file_input = $<HTMLInputElement>(
        "#realm-night-logo-upload-widget input.image_file_input",
    );
    $("#realm-day-logo-upload-widget .image-block").attr("src", realm.realm_logo_url);

    if (realm.realm_night_logo_source === "D" && realm.realm_logo_source !== "D") {
        // If no dark theme logo is uploaded but a light theme one
        // is, use the light theme one; this handles the common case
        // of transparent background logos that look good on both
        // dark and light themes.  See also similar code in admin.ts.

        $("#realm-night-logo-upload-widget .image-block").attr("src", realm.realm_logo_url);
    } else {
        $("#realm-night-logo-upload-widget .image-block").attr("src", realm.realm_night_logo_url);
    }

    const $realm_logo = $<HTMLImageElement>("#realm-navbar-wide-logo");
    if (settings_data.using_dark_theme() && realm.realm_night_logo_source !== "D") {
        $realm_logo.attr("src", realm.realm_night_logo_url);
    } else {
        $realm_logo.attr("src", realm.realm_logo_url);
    }

    $realm_logo.on("load", () => {
        const logo_width = $realm_logo.width();
        if (logo_width) {
            $("html").css(
                "--realm-logo-current-width",
                logo_width / user_settings.web_font_size_px + "em",
            );
        }
    });

    change_logo_delete_button(
        realm.realm_logo_source,
        $("#realm-day-logo-upload-widget .image-delete-button"),
        $file_input,
    );
    change_logo_delete_button(
        realm.realm_night_logo_source,
        $("#realm-night-logo-upload-widget .image-delete-button"),
        $night_file_input,
    );
}

export function initialize(): void {
    // render once
    render();

    // Rerender the realm-navbar-wide-logo when the browser detects color scheme changes.
    ui_util.listener_for_preferred_color_scheme_change(render);
}
