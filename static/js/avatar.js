var avatar = (function () {

var exports = {};

exports.build_bot_create_widget = function () {

    // We have to do strange gyrations with the file input to clear it,
    // where we replace it wholesale, so we generalize the file input with
    // a callback function.
    var get_file_input = function () {
        return $('#bot_avatar_file_input');
    };

    var file_name_field = $('#bot_avatar_file');
    var input_error = $('#bot_avatar_file_input_error');
    var clear_button = $('#bot_avatar_clear_button');
    var upload_button = $('#bot_avatar_upload_button');

    return upload_widget.build_widget(
        get_file_input,
        file_name_field,
        input_error,
        clear_button,
        upload_button
    );
};

exports.build_bot_edit_widget = function (target) {
    var get_file_input = function () {
        return target.find('.edit_bot_avatar_file_input');
    };

    var file_name_field = target.find('.edit_bot_avatar_file');
    var input_error = target.find('.edit_bot_avatar_error');
    var clear_button = target.find('.edit_bot_avatar_clear_button');
    var upload_button = target.find('.edit_bot_avatar_upload_button');

    return upload_widget.build_widget(
        get_file_input,
        file_name_field,
        input_error,
        clear_button,
        upload_button
    );
};

exports.build_user_avatar_widget = function (upload_function) {
    var get_file_input = function () {
        return $('#user_avatar_file_input').expectOne();
    };

    if (page_params.avatar_source === 'G') {
        $("#user_avatar_delete_button").hide();
        $("#user-avatar-source").show();
    } else {
        $("#user-avatar-source").hide();
    }

    $("#user_avatar_delete_button").on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        channel.del({
            url: '/json/users/me/avatar',
            success: function (data) {
              $("#user-settings-avatar").expectOne().attr("src", data.avatar_url);
              $("#user_avatar_delete_button").hide();
              $("#user-avatar-source").show();
              // Need to clear input because of a small edge case
              // where you try to upload the same image you just deleted.
              get_file_input().val('');
            },
        });
    });

    return upload_widget.build_direct_upload_widget(
            get_file_input,
            $("#user_avatar_file_input_error").expectOne(),
            $("#user_avatar_upload_button").expectOne(),
            upload_function,
            page_params.max_avatar_file_size
    );
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = avatar;
}
