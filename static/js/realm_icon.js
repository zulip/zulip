/* eslint indent: "off" */
var realm_icon = (function () {

    var exports = {};

    exports.build_realm_icon_widget = function (upload_function) {
        var elem_id = "#realm-icon-section";
        var get_file_input = function () {
            return $(elem_id + " .file_input").expectOne();
        };

        if (page_params.realm_icon_source === 'G') {
            $(elem_id + " .delete-button").hide();
        } else {
            $(elem_id + " .delete-button").show();
        }
        $(elem_id + " .delete-button").on('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            channel.del({
                url: '/json/realm/icon',
            });
        });

        return upload_widget.build_direct_upload_widget(
            get_file_input,
            $(elem_id + " .file_input_error").expectOne(),
            $(elem_id + " .upload-button").expectOne(),
            upload_function,
            page_params.max_icon_file_size
        );
    };

    exports.rerender = function () {
        var elem_id = "#realm-icon-section";
        $(elem_id + " .realm-settings-widget").attr("src", page_params.realm_icon_url);
        if (page_params.realm_icon_source === 'U') {
            $(elem_id + " .delete-button").show();
        } else {
            $(elem_id + " .delete-button").hide();
            // Need to clear input because of a small edge case
            // where you try to upload the same image you just deleted.
            var file_input = $(elem_id + " .file_input");
            file_input.val('');
        }
    };

    return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = realm_icon;
}
window.realm_icon = realm_icon;
