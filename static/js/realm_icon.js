var realm_icon = (function () {

    var exports = {};

    exports.build_realm_icon_widget = function (upload_function) {
        var get_file_input = function () {
            return $('#realm_icon_file_input').expectOne();
        };

        if (page_params.realm_icon_source === 'G') {
            $("#realm_icon_delete_button").hide();
        } else {
            $("#realm_icon_delete_button").show();
        }
        $("#realm_icon_delete_button").on('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            channel.del({
                url: '/json/realm/icon',
            });
        });

        return upload_widget.build_direct_upload_widget(
            get_file_input,
            $("#realm_icon_file_input_error").expectOne(),
            $("#realm_icon_upload_button").expectOne(),
            upload_function,
            page_params.max_icon_file_size
        );
    };

    exports.rerender = function () {
        $("#realm-settings-icon").attr("src", page_params.realm_icon_url);
        if (page_params.realm_icon_source === 'U') {
            $("#realm_icon_delete_button").show();
        } else {
            $("#realm_icon_delete_button").hide();
            // Need to clear input because of a small edge case
            // where you try to upload the same image you just deleted.
            var file_input = $("#realm_icon_file_input");
            file_input.val('');
        }
    };

    return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = realm_icon;
}
