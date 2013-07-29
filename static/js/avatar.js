var avatar = (function () {

var exports = {};

function is_image_format(file) {
    var type = file.type;
    if (!type) return false;

    var supported_types = [
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/svg+xml'
    ];
    return $.inArray(type, supported_types) >= 0;
}

exports.set_up_avatar_logic_for_creating_bots = function () {

    function accept_bot_avatar_file_input(file) {
        $('#bot_avatar_file').text(file.name);
        $('#bot_avatar_file_input_error').hide();
        $('#bot_avatar_clear_button').show();
        $('#bot_avatar_upload_button').hide();
    }

    function clear_bot_avatar_file_input() {
        var control = $('#bot_avatar_file_input');
        var new_control = control.clone(true);
        control.replaceWith(new_control);
        $('#bot_avatar_file').text('');
        $('#bot_avatar_clear_button').hide();
        $('#bot_avatar_upload_button').show();
    }

    $('#bot_avatar_clear_button').click(function (e) {
        clear_bot_avatar_file_input();
        e.preventDefault();
    });

    $('#bot_avatar_upload_button').on('drop', function (e) {
        var files = e.dataTransfer.files;
        if (files === null || files === undefined || files.length === 0) {
            return false;
        }
        $('#bot_avatar_file_input').get(0).files = files;
        e.preventDefault();
        return false;
    });

    var validate_avatar = function (e) {
        if (e.target.files.length === 0) {
            $('#bot_avatar_file_input_error').hide();
        } else if (e.target.files.length === 1) {
            var file = e.target.files[0];
            if (file.size > 5*1024*1024) {
                $('#bot_avatar_file_input_error').text('File size must be < 5Mb.');
                $('#bot_avatar_file_input_error').show();
                clear_bot_avatar_file_input();
            }
            else if (!is_image_format(file)) {
                $('#bot_avatar_file_input_error').text('File type is not supported.');
                $('#bot_avatar_file_input_error').show();
                clear_bot_avatar_file_input();
            } else {
                accept_bot_avatar_file_input(file);
            }
        }
        else {
            $('#bot_avatar_file_input_error').text('Please just upload one file.');
        }
    };

    $('#bot_avatar_file_input').change(validate_avatar);

    $('#bot_avatar_upload_button').click(function (e) {
        $('#bot_avatar_file_input').trigger('click');
        e.preventDefault();
    });

    return clear_bot_avatar_file_input;
};

return exports;

}());
