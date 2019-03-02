/* eslint indent: "off" */
var realm_logo = (function () {

    var exports = {};
    exports.build_realm_logo_widget = function (upload_function) {
        var get_file_input = function () {
            return $('#realm_logo_file_input').expectOne();
        };
        if (page_params.realm_logo_source === 'D') {
            $("#realm_logo_delete_button").hide();
        } else {
            $("#realm_logo_delete_button").show();
        }
        var data = {night: JSON.stringify(false)};
        $("#realm_logo_delete_button").on('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            channel.del({
                url: '/json/realm/logo',
                data: data,
            });
        });

        return upload_widget.build_direct_upload_widget(
            get_file_input,
            $("#realm_logo_file_input_error").expectOne(),
            $("#realm_logo_upload_button").expectOne(),
            upload_function,
            page_params.max_logo_file_size
        );
    };

    exports.build_realm_night_logo_widget = function (upload_function) {
        var get_file_input = function () {
            return $('#realm_night_logo_file_input').expectOne();
        };
        if (page_params.realm_night_logo_source === 'D') {
            $("#realm_night_logo_delete_button").hide();
        } else {
            $("#realm_night_logo_delete_button").show();
        }
        var data = {night: JSON.stringify(true)};
        $("#realm_night_logo_delete_button").on('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            channel.del({
                url: '/json/realm/logo',
                data: data,
            });
        });

        return upload_widget.build_direct_upload_widget(
            get_file_input,
            $("#realm_night_logo_file_input_error").expectOne(),
            $("#realm_night_logo_upload_button").expectOne(),
            upload_function,
            page_params.max_logo_file_size
        );
    };

    exports.rerender = function () {
        var file_input = $("#realm_logo_file_input");
        var night_file_input = $("#realm_night_logo_file_input");
        $("#realm-settings-logo").attr("src", page_params.realm_logo_url);

        if (page_params.realm_night_logo_source === 'D' &&
            page_params.realm_logo_source !== 'D') {
            // If no night mode logo is uploaded but a day mode one
            // is, use the day mode one; this handles the common case
            // of transparent background logos that look good on both
            // night and day themes.  See also similar code in admin.js.

            $("#realm-settings-night-logo").attr("src", page_params.realm_logo_url);
        } else {
            $("#realm-settings-night-logo").attr("src", page_params.realm_night_logo_url);
        }

        if (page_params.night_mode && page_params.realm_night_logo_source !== 'D') {
            $("#realm-logo").attr("src", page_params.realm_night_logo_url);
        } else {
            $("#realm-logo").attr("src", page_params.realm_logo_url);
        }
        if (page_params.realm_logo_source === 'U') {
            $("#realm_logo_delete_button").show();
        } else {
            $("#realm_logo_delete_button").hide();
            // Need to clear input because of a small edge case
            // where you try to upload the same image you just deleted.
            file_input.val('');
        }
        if (page_params.realm_night_logo_source === 'U') {
            $("#realm_night_logo_delete_button").show();
        } else {
            $("#realm_night_logo_delete_button").hide();
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
