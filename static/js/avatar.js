var avatar = (function () {

var exports = {};

function is_image_format(file) {
    var type = file.type;
    if (!type) {
        return false;
    }

    var supported_types = [
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/tiff'
    ];
    return _.indexOf(supported_types, type) >= 0;
}

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

    return exports.build_widget(
        get_file_input,
        file_name_field,
        input_error,
        clear_button,
        upload_button
    );
};

exports.build_bot_edit_widget = function (li) {
    var get_file_input = function () {
        return li.find('.edit_bot_avatar_file_input');
    };

    var file_name_field = li.find('.edit_bot_avatar_file');
    var input_error = li.find('.edit_bot_avatar_error');
    var clear_button = li.find('.edit_bot_avatar_clear_button');
    var upload_button = li.find('.edit_bot_avatar_upload_button');

    return exports.build_widget(
        get_file_input,
        file_name_field,
        input_error,
        clear_button,
        upload_button
    );
};

exports.build_widget = function (
        get_file_input, // function returns a jQuery file input object
        file_name_field, // jQuery object to show file name
        input_error, // jQuery object for error text
        clear_button, // jQuery button to clear last upload choice
        upload_button // jQuery button to open file dialog
) {

    function accept(file) {
        file_name_field.text(file.name);
        input_error.hide();
        clear_button.show();
        upload_button.hide();
    }

    function clear() {
        var control = get_file_input();
        var new_control = control.clone(true);
        control.replaceWith(new_control);
        file_name_field.text('');
        clear_button.hide();
        upload_button.show();
    }

    clear_button.on('click', function (e) {
        clear();
        e.preventDefault();
    });

    upload_button.on('drop', function (e) {
        var files = e.dataTransfer.files;
        if (files === null || files === undefined || files.length === 0) {
            return false;
        }
        get_file_input().get(0).files = files;
        e.preventDefault();
        return false;
    });

    get_file_input().on('change', function (e) {
        if (e.target.files.length === 0) {
            input_error.hide();
        } else if (e.target.files.length === 1) {
            var file = e.target.files[0];
            if (file.size > 5*1024*1024) {
                input_error.text('File size must be < 5Mb.');
                input_error.show();
                clear();
            } else if (!is_image_format(file)) {
                input_error.text('File type is not supported.');
                input_error.show();
                clear();
            } else {
                accept(file);
            }
        } else {
            input_error.text('Please just upload one file.');
        }
    });

    upload_button.on('click', function (e) {
        get_file_input().trigger('click');
        e.preventDefault();
    });

    function close() {
        clear();
        clear_button.off('click');
        upload_button.off('drop');
        get_file_input().off('change');
        upload_button.off('click');
    }

    return {
        // Call back to clear() in situations like adding bots, when
        // we want to use the same widget over and over again.
        clear: clear,
        // Call back to close() when you are truly done with the widget,
        // so you can release handlers.
        close: close
    };
};

exports.build_user_avatar_widget = function (upload_function) {
    var get_file_input = function () {
        return $('#user_avatar_file_input').expectOne();
    };

    if (page_params.avatar_source === 'G') {
        $("#user_avatar_delete_button").hide();
    }
    $("#user_avatar_delete_button").on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        channel.del({
            url: '/json/users/me/avatar',
            success: function (data) {
              $("#user-settings-avatar").expectOne().attr("src", data.avatar_url);
              $("#user_avatar_delete_button").hide();
              // Need to clear input because of a small edge case
              // where you try to upload the same image you just deleted.
              var file_input = $("#user_avatar_file_input");
              file_input.replaceWith(file_input.clone(true));
            }
        });
    });

    return exports.build_direct_upload_widget(
            get_file_input,
            $("#user_avatar_file_input_error").expectOne(),
            $("#user_avatar_upload_button").expectOne(),
            upload_function
    );
};

exports.build_direct_upload_widget = function (
        get_file_input, // function returns a jQuery file input object
        input_error, // jQuery object for error text
        upload_button, // jQuery button to open file dialog
        upload_function
) {

    function accept() {
        input_error.hide();
        upload_function(get_file_input());
    }

    function clear() {
        var control = get_file_input();
        var new_control = control.clone(true);
        control.replaceWith(new_control);
    }

    upload_button.on('drop', function (e) {
        var files = e.dataTransfer.files;
        if (files === null || files === undefined || files.length === 0) {
            return false;
        }
        get_file_input().get(0).files = files;
        e.preventDefault();
        return false;
    });

    get_file_input().on('change', function (e) {
        if (e.target.files.length === 0) {
            input_error.hide();
        } else if (e.target.files.length === 1) {
            var file = e.target.files[0];
            if (file.size > 5*1024*1024) {
                input_error.text('File size must be < 5Mb.');
                input_error.show();
                clear();
            } else if (!is_image_format(file)) {
                input_error.text('File type is not supported.');
                input_error.show();
                clear();
            } else {
                accept(file);
            }
        } else {
            input_error.text('Please just upload one file.');
        }
    });

    upload_button.on('click', function (e) {
        get_file_input().trigger('click');
        e.preventDefault();
    });
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = avatar;
}
