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
        $("#realm_logo_delete_button").on('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            channel.del({
                url: '/json/realm/logo',
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

    exports.rerender = function () {
        $("#realm-settings-logo").attr("src", page_params.realm_logo_url);
        $("#realm-logo").attr("src", page_params.realm_logo_url);
        if (page_params.realm_logo_source === 'U') {
            $("#realm_logo_delete_button").show();
        } else {
            $("#realm_logo_delete_button").hide();
            // Need to clear input because of a small edge case
            // where you try to upload the same image you just deleted.
            var file_input = $("#realm_logo_file_input");
            file_input.val('');
        }
    };

    return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = realm_logo;
}
window.realm_logo = realm_logo;
