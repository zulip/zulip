var settings = (function () {

var exports = {};

function add_bot_row(name, email, avatar_url, api_key) {
    var info = {
        name: name,
        email: email,
        avatar_url: avatar_url,
        api_key: api_key
    };

    var row = $(templates.render('bot_avatar_row', info));
    $('#bots_list').append(row);
    $('#bots_list').show();
}

function is_local_part(value, element) {
    // Adapted from Django's EmailValidator
    return this.optional(element) || /^[\-!#$%&'*+\/=?\^_`{}|~0-9A-Z]+(\.[\-!#$%&'*+\/=?\^_`{}|~0-9A-Z]+)*$/i.test(value);
}

$(function () {
    $.ajax({
        type: 'POST',
        url: '/json/get_bots',
        dataType: 'json',
        success: function (data) {
            $('#bot_table_error').hide();

            $.each(data.bots, function (idx, elem) {
                add_bot_row(elem.full_name, elem.username, elem.avatar_url, elem.api_key);
            });
        },
        error: function (xhr, error_type, xhn) {
            $('#bot_table_error').text("Could not fetch bots list").show();
        }
    });

    $.validator.addMethod("bot_local_part",
                          function (value, element) {
                              return is_local_part.call(this, value + "-bot", element);
                          },
                          "Please only use characters that are valid in an email address");


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

    $('#bot_avatar_file_input').change(function (e) {
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
    });

    $('#bot_avatar_upload_button').click(function (e) {
        $('#bot_avatar_file_input').trigger('click');
        e.preventDefault();
    });

    $('#create_bot_form').validate({
        errorClass: 'text-error',
        success: function () {
            $('#bot_table_error').hide();
        },
        submitHandler: function () {
            var full_name = $('#create_bot_name').val();
            var short_name = $('#create_bot_short_name').val();
            var formData = new FormData();
            formData.append('csrfmiddlewaretoken', csrf_token);
            formData.append('full_name', full_name);
            formData.append('short_name', short_name);
            jQuery.each($('#bot_avatar_file_input')[0].files, function (i, file) {
                formData.append('file-'+i, file);
            });
            util.make_loading_indicator($('#create_bot_spinner'), {text: 'Adding bot'});
            $('#create_bot_button').hide();
            $.ajax({
                url: '/json/create_bot',
                type: 'POST',
                data: formData,
                cache: false,
                processData: false,
                contentType: false,
                success: function (data) {
                    util.destroy_loading_indicator($("#create_bot_spinner"));
                    $('#bot_table_error').hide();
                    $('#create_bot_name').val('');
                    $('#create_bot_short_name').val('');
                    $('#create_bot_button').show();
                    clear_bot_avatar_file_input();

                    add_bot_row(
                            full_name,
                            short_name + "-bot@" + page_params.domain,
                            data.avatar_url,
                            data.api_key
                    );
                },
                error: function (xhr, error_type, exn) {
                    util.destroy_loading_indicator($("#create_bot_spinner"));
                    $('#create_bot_button').show();
                    $('#bot_table_error').text(JSON.parse(xhr.responseText).msg).show();
                }
            });
        }
    });

    $("#bots_list").on("click", "button.delete_bot", function (e) {
        var email = $(e.target).data('email');
        $.ajax({
            url: '/json/users/' + encodeURIComponent(email),
            type: 'DELETE',
            success: function () {
                var row = $(e.target).closest("li");
                row.hide('slow', function () { row.remove(); });
            },
            error: function (xhr) {
                $('#bot_delete_error').text(JSON.parse(xhr.responseText).msg).show();
            }
        });
    });

    $("#bots_list").on("click", "button.regenerate_bot_api_key", function (e) {
        var email = $(e.target).data('email');
        $.ajax({
            url: '/json/bots/' + encodeURIComponent(email) + '/api_key/regenerate',
            type: 'POST',
            success: function (data) {
                var row = $(e.target).closest("li");
                row.find(".api_key").find(".value").text(data.api_key);
                row.find("api_key_error").hide();
            },
            error: function (xhr) {
                var row = $(e.target).closest("li");
                row.find(".api_key_error").text(JSON.parse(xhr.responseText).msg).show();
            }
        });
    });


    $("#bots_list").on("click", "button.open_edit_bot_form", function (e) {
        var li = $(e.target).closest('li');
        var edit_div = li.find('div.edit_bot');
        var form = li.find('.edit_bot_form');
        var image = li.find(".image");
        var bot_info = li.find(".bot_info");
        var reset_edit_bot = li.find(".reset_edit_bot");

        var old_full_name = bot_info.find(".name").text();
        form.find(".edit_bot_name").attr('value', old_full_name);

        image.hide();
        bot_info.hide();
        edit_div.show();

        function show_row_again() {
            image.show();
            bot_info.show();
            edit_div.hide();
        }

        reset_edit_bot.click(function (event) {
            show_row_again();
            $(this).off(event);
        });

        var errors = form.find('.bot_edit_errors');

        form.validate({
            errorClass: 'text-error',
            success: function (label) {
                errors.hide();
            },
            submitHandler: function () {
                var email = form.data('email');
                var full_name = form.find('.edit_bot_name').val();
                var spinner = form.find('.edit_bot_spinner');
                var edit_button = form.find('.edit_bot_button');
                var formData = new FormData();
                formData.append('full_name', full_name);
                formData.append('csrfmiddlewaretoken', csrf_token);
                util.make_loading_indicator(spinner, {text: 'Editing bot'});
                edit_button.hide();
                $.ajax({
                    url: '/json/bots/' + encodeURIComponent(email),
                    type: 'PATCH',
                    data: formData,
                    cache: false,
                    processData: false,
                    contentType: false,
                    success: function (data) {
                        util.destroy_loading_indicator(spinner);
                        errors.hide();
                        edit_button.show();
                        show_row_again();
                        bot_info.find('.name').text(full_name);
                    },
                    error: function (xhr, error_type, exn) {
                        util.destroy_loading_indicator(spinner);
                        edit_button.show();
                        errors.text(JSON.parse(xhr.responseText).msg).show();
                    }
                });
            }
        });


    });



});

}());
