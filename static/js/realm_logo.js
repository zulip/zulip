"use strict";

const settings_config = require("./settings_config");

exports.build_realm_logo_widget = function (upload_function, is_night) {
    let logo_section_id = "#realm-day-logo-upload-widget";
    let logo_source = page_params.realm_logo_source;

    if (is_night) {
        logo_section_id = "#realm-night-logo-upload-widget";
        logo_source = page_params.realm_night_logo_source;
    }

    const delete_button_elem = $(logo_section_id + " .image-delete-button");
    const file_input_elem = $(logo_section_id + " .image_file_input");
    const file_input_error_elem = $(logo_section_id + " .image_file_input_error");
    const upload_button_elem = $(logo_section_id + " .image_upload_button");

    const get_file_input = function () {
        return file_input_elem.expectOne();
    };

    if (!page_params.is_admin) {
        return undefined;
    }

    if (logo_source === "D") {
        delete_button_elem.hide();
    } else {
        delete_button_elem.show();
    }

    const data = {night: JSON.stringify(is_night)};
    delete_button_elem.on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        channel.del({
            url: "/json/realm/logo",
            data,
        });
    });

    return upload_widget.build_direct_upload_widget(
        get_file_input,
        file_input_error_elem.expectOne(),
        upload_button_elem.expectOne(),
        upload_function,
        page_params.max_logo_file_size,
    );
};

function change_logo_delete_button(logo_source, logo_delete_button, file_input) {
    if (logo_source === "U") {
        logo_delete_button.show();
    } else {
        logo_delete_button.hide();
        // Need to clear input because of a small edge case
        // where you try to upload the same image you just deleted.
        file_input.val("");
    }
}

exports.rerender = function () {
    const file_input = $("#realm-day-logo-upload-widget .image_file_input");
    const night_file_input = $("#realm-night-logo-upload-widget .realm-logo-file-input");
    $("#realm-day-logo-upload-widget .image-block").attr("src", page_params.realm_logo_url);

    if (page_params.realm_night_logo_source === "D" && page_params.realm_logo_source !== "D") {
        // If no night mode logo is uploaded but a day mode one
        // is, use the day mode one; this handles the common case
        // of transparent background logos that look good on both
        // night and day themes.  See also similar code in admin.js.

        $("#realm-night-logo-upload-widget .image-block").attr("src", page_params.realm_logo_url);
    } else {
        $("#realm-night-logo-upload-widget .image-block").attr(
            "src",
            page_params.realm_night_logo_url,
        );
    }

    if (
        (page_params.color_scheme === settings_config.color_scheme_values.night.code &&
            page_params.realm_night_logo_source !== "D") ||
        (page_params.color_scheme === settings_config.color_scheme_values.automatic.code &&
            page_params.realm_night_logo_source !== "D" &&
            window.matchMedia &&
            window.matchMedia("(prefers-color-scheme: dark)").matches)
    ) {
        $("#realm-logo").attr("src", page_params.realm_night_logo_url);
    } else {
        $("#realm-logo").attr("src", page_params.realm_logo_url);
    }

    change_logo_delete_button(
        page_params.realm_logo_source,
        $("#realm-day-logo-upload-widget .image-delete-button"),
        file_input,
    );
    change_logo_delete_button(
        page_params.realm_night_logo_source,
        $("#realm-night-logo-upload-widget .image-delete-button"),
        night_file_input,
    );
};

window.realm_logo = exports;
