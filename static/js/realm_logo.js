/* eslint indent: "off" */
var realm_logo = (function () {
    var exports = {};
    exports.build_realm_logo_widget = function (upload_function, is_night) {
        var elem_id = "#realm-logo-section";
        var source = page_params.realm_logo_source;
        if (is_night) {
            elem_id = "#realm-night-logo-section";
            source = page_params.realm_night_logo_source;
        }

        var get_file_input = function () {
            return $(elem_id + " .file_input").expectOne();
        };
        if (source === 'D') {
            $(elem_id + " .delete-button").hide();
        } else {
            $(elem_id + " .delete-button").show();
        }
        var data = {night: JSON.stringify(is_night)};
        $(elem_id + " .delete-button").on('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            channel.del({
                url: '/json/realm/logo',
                data: data,
            });
        });

        return upload_widget.build_direct_upload_widget(
            get_file_input,
            $(elem_id + " .file_input_error").expectOne(),
            $(elem_id + " .upload-button").expectOne(),
            upload_function,
            page_params.max_logo_file_size
        );
    };

    exports.rerender = function () {
        var logo_elem_id = "#realm-logo-section";
        var night_logo_elem_id = "#realm-night-logo-section";
        var file_input = $(logo_elem_id + " .file_input");
        var night_file_input = $(night_logo_elem_id + " .file_input");
        $(logo_elem_id + " .realm-settings-widget").attr("src", page_params.realm_logo_url);

        if (page_params.realm_night_logo_source === 'D' &&
            page_params.realm_logo_source !== 'D') {
            // If no night mode logo is uploaded but a day mode one
            // is, use the day mode one; this handles the common case
            // of transparent background logos that look good on both
            // night and day themes.  See also similar code in admin.js.

            $(night_logo_elem_id + " .realm-settings-widget").attr("src", page_params.realm_logo_url);
        } else {
            $(night_logo_elem_id + " .realm-settings-widget").attr("src", page_params.realm_night_logo_url);
        }

        if (page_params.night_mode && page_params.realm_night_logo_source !== 'D') {
            $("#realm-logo").attr("src", page_params.realm_night_logo_url);
        } else {
            $("#realm-logo").attr("src", page_params.realm_logo_url);
        }
        if (page_params.realm_logo_source === 'U') {
            $(logo_elem_id + " .delete-button").show();
        } else {
            $(logo_elem_id + " .delete-button").hide();
            // Need to clear input because of a small edge case
            // where you try to upload the same image you just deleted.
            file_input.val('');
        }
        if (page_params.realm_night_logo_source === 'U') {
            $(night_logo_elem_id + " .delete-button").show();
        } else {
            $(night_logo_elem_id + " .delete-button").hide();
            // Need to clear input because of a small edge case
            // where you try to upload the same image you just deleted.
            night_file_input.val('');
        }

    };

    return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = realm_logo;
}
window.realm_logo = realm_logo;
