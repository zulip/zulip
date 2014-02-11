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

// Choose avatar stamp fairly randomly, to help get old avatars out of cache.
exports.avatar_stamp = Math.floor(Math.random()*100);

$(function () {

    if (!feature_flags.show_digest_email_setting) {
        $("#digest_container").hide();
    }

    function upload_avatar(file_input) {
        var form_data = new FormData();

        form_data.append('csrfmiddlewaretoken', csrf_token);
        jQuery.each(file_input[0].files, function (i, file) {
            form_data.append('file-'+i, file);
        });

        var spinner = $("#upload_avatar_spinner").expectOne();
        util.make_loading_indicator(spinner, {text: 'Uploading avatar.'});

        channel.post({
            url: '/json/set_avatar',
            data: form_data,
            cache: false,
            processData: false,
            contentType: false,
            success: function (data) {
                util.destroy_loading_indicator($("#upload_avatar_spinner"));
                var url = data.avatar_url + '&stamp=' + exports.avatar_stamp;
                $("#user-settings-avatar").expectOne().attr("src", url);
                exports.avatar_stamp += 1;
            }
        });

    }

    avatar.build_user_avatar_widget(upload_avatar);

    if (page_params.domain === "users.customer4.invalid" ||
        page_params.name_changes_disabled) {
        // At the request of the facilitators, CUSTOMER4 users
        // can't change their names, so don't show that as a settings
        // option. This is also disabled through the JSON UI. Once we
        // have the infrastructure for administrative policies, we can
        // handle this more gracefully.
        //
        // Additionally, if this install has disabled name changes, hide the
        // container
        $("#name_change_container").hide();
    }

    channel.get({
        url: '/json/bots',
        idempotent: true,
        success: function (data) {
            $('#bot_table_error').hide();

            _.each(data.bots, function (elem) {
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


    var create_avatar_widget = avatar.build_bot_create_widget();

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
            $('#create_bot_button').val('Adding bot...').prop('disabled', true);
            channel.post({
                url: '/json/bots',
                data: formData,
                cache: false,
                processData: false,
                contentType: false,
                success: function (data) {
                    $('#bot_table_error').hide();
                    $('#create_bot_name').val('');
                    $('#create_bot_short_name').val('');
                    $('#create_bot_button').show();
                    create_avatar_widget.clear();

                    add_bot_row(
                            full_name,
                            short_name + "-bot@" + page_params.domain,
                            data.avatar_url,
                            data.api_key
                    );
                },
                error: function (xhr, error_type, exn) {
                    $('#bot_table_error').text(JSON.parse(xhr.responseText).msg).show();
                },
                complete: function (xhr, status) {
                    $('#create_bot_button').val('Create bot').prop('disabled', false);
                }
            });
        }
    });

    $("#bots_list").on("click", "button.delete_bot", function (e) {
        var email = $(e.currentTarget).data('email');
        channel.del({
            url: '/json/bots/' + encodeURIComponent(email),
            success: function () {
                var row = $(e.currentTarget).closest("li");
                row.hide('slow', function () { row.remove(); });
            },
            error: function (xhr) {
                $('#bot_delete_error').text(JSON.parse(xhr.responseText).msg).show();
            }
        });
    });

    $("#bots_list").on("click", "button.regenerate_bot_api_key", function (e) {
        var email = $(e.currentTarget).data('email');
        channel.post({
            url: '/json/bots/' + encodeURIComponent(email) + '/api_key/regenerate',
            idempotent: true,
            success: function (data) {
                var row = $(e.currentTarget).closest("li");
                row.find(".api_key").find(".value").text(data.api_key);
                row.find("api_key_error").hide();
            },
            error: function (xhr) {
                var row = $(e.currentTarget).closest("li");
                row.find(".api_key_error").text(JSON.parse(xhr.responseText).msg).show();
            }
        });
    });

    var image_version = 0;

    $("#bots_list").on("click", "button.open_edit_bot_form", function (e) {
        var li = $(e.currentTarget).closest('li');
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

        var avatar_widget = avatar.build_bot_edit_widget(li);

        function show_row_again() {
            image.show();
            bot_info.show();
            edit_div.hide();
            avatar_widget.close();
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
                var file_input = li.find('.edit_bot_avatar_file_input');
                var spinner = form.find('.edit_bot_spinner');
                var edit_button = form.find('.edit_bot_button');
                var formData = new FormData();
                formData.append('full_name', full_name);
                formData.append('csrfmiddlewaretoken', csrf_token);
                jQuery.each(file_input[0].files, function (i, file) {
                    formData.append('file-'+i, file);
                });
                util.make_loading_indicator(spinner, {text: 'Editing bot'});
                edit_button.hide();
                channel.patch({
                    url: '/json/bots/' + encodeURIComponent(email),
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
                        if (data.avatar_url) {
                            // Note that the avatar_url won't actually change on the back end
                            // when the user had a previous uploaded avatar.  Only the content
                            // changes, so we version it to get an uncached copy.
                            image_version += 1;
                            image.find('img').attr('src', data.avatar_url+'&v='+image_version.toString());
                        }
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

    $("#show_api_key_box").on("click", "button.regenerate_api_key", function (e) {
        channel.post({
            url: '/json/users/me/api_key/regenerate',
            idempotent: true,
            success: function (data) {
                $('#api_key_value').text(data.api_key);
            },
            error: function (xhr) {
                $('#user_api_key_error').text(JSON.parse(xhr.responseText).msg).show();
            }
        });
    });

});

return exports;
}());
