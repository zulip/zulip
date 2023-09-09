import $ from "jquery";

import * as channel from "./channel";
import {page_params} from "./page_params";
import * as settings_data from "./settings_data";
import * as ui_util from "./ui_util";
import * as upload_widget from "./upload_widget";
import type {UploadFunction} from "./upload_widget";

export function build_realm_logo_widget(upload_function: UploadFunction, is_night: boolean): void {
    let logo_section_id = "#realm-day-logo-upload-widget";
    let logo_source = page_params.realm_logo_source;

    if (is_night) {
        logo_section_id = "#realm-night-logo-upload-widget";
        logo_source = page_params.realm_night_logo_source;
    }

    const $delete_button_elem = $(logo_section_id + " .image-delete-button");
    const $file_input_elem = $<HTMLInputElement>(logo_section_id + " .image_file_input");
    const $file_input_error_elem = $(logo_section_id + " .image_file_input_error");
    const $upload_button_elem = $(logo_section_id + " .image_upload_button");

    const get_file_input = function (): JQuery<HTMLInputElement> {
        return $file_input_elem.expectOne();
    };

    if (!page_params.is_admin) {
        return undefined;
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

    return upload_widget.build_direct_upload_widget(
        get_file_input,
        $file_input_error_elem.expectOne(),
        $upload_button_elem.expectOne(),
        upload_function,
        page_params.max_logo_file_size_mib,
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
    const $file_input = $<HTMLInputElement>("#realm-day-logo-upload-widget .image_file_input");
    const $night_file_input = $<HTMLInputElement>(
        "#realm-night-logo-upload-widget .realm-logo-file-input",
    );
    $("#realm-day-logo-upload-widget .image-block").attr("src", page_params.realm_logo_url);

    if (page_params.realm_night_logo_source === "D" && page_params.realm_logo_source !== "D") {
        // If no dark theme logo is uploaded but a light theme one
        // is, use the light theme one; this handles the common case
        // of transparent background logos that look good on both
        // dark and light themes.  See also similar code in admin.js.

        $("#realm-night-logo-upload-widget .image-block").attr("src", page_params.realm_logo_url);
    } else {
        $("#realm-night-logo-upload-widget .image-block").attr(
            "src",
            page_params.realm_night_logo_url,
        );
    }

    if (settings_data.using_dark_theme() && page_params.realm_night_logo_source !== "D") {
        $("#realm-logo").attr("src", page_params.realm_night_logo_url);
    } else {
        $("#realm-logo").attr("src", page_params.realm_logo_url);
    }

    change_logo_delete_button(
        page_params.realm_logo_source,
        $("#realm-day-logo-upload-widget .image-delete-button"),
        $file_input,
    );
    change_logo_delete_button(
        page_params.realm_night_logo_source,
        $("#realm-night-logo-upload-widget .image-delete-button"),
        $night_file_input,
    );
}

export function initialize(): void {
    // render once
    render();

    // Rerender the realm-logo when the browser detects color scheme changes.
    ui_util.listener_for_preferred_color_scheme_change(render);
}
