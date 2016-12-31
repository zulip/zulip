var settings = (function () {

var exports = {};
var _streams_deferred = $.Deferred();
var streams = _streams_deferred.promise(); // promise to the full stream list

function build_stream_list($select, extra_names) {
    if (extra_names === undefined) {
        extra_names = [];
    }

    streams.done(function (stream_items) {
        var build_option = function (value_name) {
            return $('<option>')
                .attr('value', value_name[0])
                .text(value_name[1]);
        };

        var public_names = _.chain(stream_items)
            .where({invite_only: false})
            .pluck('name')
            .map(function (x) { return [x, x]; })
            .value();
        var public_options = _.chain(extra_names.concat(public_names))
            .map(build_option)
            .reduce(
                function ($optgroup, option) { return $optgroup.append(option); },
                $('<optgroup label="Public"/>')
            )
            .value();

        var private_options = _.chain(stream_items)
            .where({invite_only: true})
            .pluck('name')
            .map(function (x) { return [x, x]; })
            .map(build_option)
            .reduce(
                function ($optgroup, option) { return $optgroup.append(option); },
                $('<optgroup label="Private"/>')
            )
            .value();

        $select.empty();
        $select.append(public_options);
        $select.append(private_options);

    });
}

function add_bot_row(info) {
    info.id_suffix = _.uniqueId('_bot_');
    var row = $(templates.render('bot_avatar_row', info));
    var default_sending_stream_select = row.find('select[name=bot_default_sending_stream]');
    var default_events_register_stream_select = row.find('select[name=bot_default_events_register_stream]');

    if (!feature_flags.new_bot_ui) {
        row.find('.new-bot-ui').hide();
    }

    var to_extra_options = [];
    if (info.default_sending_stream === null) {
        to_extra_options.push(['', 'No default selected']);
    }
    build_stream_list(
        default_sending_stream_select,
        to_extra_options
    );
    default_sending_stream_select.val(
        info.default_sending_stream,
        to_extra_options
    );

    var events_extra_options = [['__all_public__', 'All public streams']];
    if (info.default_events_register_stream === null && !info.default_all_public_streams) {
        events_extra_options.unshift(['', 'No default selected']);
    }
    build_stream_list(
        default_events_register_stream_select,
        events_extra_options
    );
    if (info.default_all_public_streams) {
        default_events_register_stream_select.val('__all_public__');
    } else {
        default_events_register_stream_select.val(info.default_events_register_stream);
    }

    $('#bots_list').append(row);
    $('#bots_list').show();
}

function add_bot_default_streams_to_form(formData, default_sending_stream,
                                         default_events_register_stream) {
    if (!feature_flags.new_bot_ui) { return; }

    if (default_sending_stream !== '') {
        formData.append('default_sending_stream', default_sending_stream);
    }
    if (default_events_register_stream === '__all_public__') {
        formData.append('default_all_public_streams', JSON.stringify(true));
        formData.append('default_events_register_stream', null);
    } else if (default_events_register_stream !== '') {
        formData.append('default_all_public_streams', JSON.stringify(false));
        formData.append('default_events_register_stream', default_events_register_stream);
    }
}

function is_local_part(value, element) {
    // Adapted from Django's EmailValidator
    return this.optional(element) || /^[\-!#$%&'*+\/=?\^_`{}|~0-9A-Z]+(\.[\-!#$%&'*+\/=?\^_`{}|~0-9A-Z]+)*$/i.test(value);
}

function render_bots() {
    $('#bots_list').empty();
    _.each(bot_data.get_editable(), function (elem) {
        add_bot_row({
            name: elem.full_name,
            email: elem.email,
            avatar_url: elem.avatar_url,
            api_key: elem.api_key,
            zuliprc: 'zuliprc', // Most browsers do not allow filename starting with `.`
            default_sending_stream: elem.default_sending_stream,
            default_events_register_stream: elem.default_events_register_stream,
            default_all_public_streams: elem.default_all_public_streams
        });
    });
}

exports.generate_zuliprc_uri = function (email, api_key) {
    var data = settings.generate_zuliprc_content(email, api_key);

    return "data:application/octet-stream;charset=utf-8," + encodeURIComponent(data);
};

exports.generate_zuliprc_content = function (email, api_key) {
    return "[api]" +
           "\nemail=" + email +
           "\nkey=" + api_key +
           "\nsite=" + page_params.realm_uri +
           // Some tools would not work in files without a trailing new line.
           "\n";
};

// Choose avatar stamp fairly randomly, to help get old avatars out of cache.
exports.avatar_stamp = Math.floor(Math.random()*100);

function _setup_page() {
    // To build the edit bot streams dropdown we need both the bot and stream
    // API results. To prevent a race streams will be initialized to a promise
    // at page load. This promise will be resolved with a list of streams after
    // the first settings page load. build_stream_list then adds a callback to
    // the promise, which in most cases will already be resolved.
    if (_streams_deferred.state() !== "resolved") {
        channel.get({
            url: '/json/streams',
            success: function (data) {
                _streams_deferred.resolve(data.streams);

                build_stream_list($('#create_bot_default_sending_stream'));
                build_stream_list(
                    $('#create_bot_default_events_register_stream'),
                    [['__all_public__', 'All public streams']]
                );
            }
        });
    }

    // Most browsers do not allow filenames to start with `.` without the user manually changing it.
    var settings_tab = templates.render('settings_tab', {page_params: page_params, zuliprc: 'zuliprc'});
    $("#settings").html(settings_tab);
    $("#settings-status").hide();
    $("#notify-settings-status").hide();
    $("#display-settings-status").hide();
    $("#ui-settings-status").hide();

    alert_words_ui.set_up_alert_words();

    $("#api_key_value").text("");
    $("#get_api_key_box").hide();
    $("#show_api_key_box").hide();
    $("#api_key_button_box").show();

    function clear_password_change() {
        // Clear the password boxes so that passwords don't linger in the DOM
        // for an XSS attacker to find.
        $('#old_password, #new_password, #confirm_password').val('');
    }

    clear_password_change();

    $('#api_key_button').click(function () {
        if (page_params.password_auth_enabled !== false) {
            $("#get_api_key_box").show();
        } else {
            // Skip the password prompt step
            $("#get_api_key_box form").submit();
        }
        $("#api_key_button_box").hide();
    });

    $('#pw_change_link').on('click', function (e) {
        e.preventDefault();
        $('#pw_change_link').hide();
        $('#pw_change_controls').show();
        if (page_params.password_auth_enabled !== false) {
            // zxcvbn.js is pretty big, and is only needed on password
            // change, so load it asynchronously.
            $.getScript('/static/node_modules/zxcvbn/dist/zxcvbn.js', function () {
                $('#pw_strength .bar').removeClass("fade");
            });
        }
    });

    $('#new_password').on('change keyup', function () {
        password_quality($('#new_password').val(), $('#pw_strength .bar'));
    });

    if (!page_params.show_digest_email) {
        $("#other_notifications").hide();
    }
    if (!feature_flags.new_bot_ui) {
        $('.new-bot-ui').hide();
    }

    function settings_change_error(message, xhr) {
        // Scroll to the top so the error message is visible.
        // We would scroll anyway if we end up submitting the form.
        viewport.scrollTop(0);
        ui.report_error(message, xhr, $('#settings-status').expectOne());
    }

    function settings_change_success(message) {
        // Scroll to the top so the error message is visible.
        // We would scroll anyway if we end up submitting the form.
        viewport.scrollTop(0);
        ui.report_success(message, $('#settings-status').expectOne());
    }

    $("form.your-account-settings").ajaxForm({
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        beforeSubmit: function () {
            if (page_params.password_auth_enabled !== false) {
                // FIXME: Check that the two password fields match
                // FIXME: Use the same jQuery validation plugin as the signup form?
                var new_pw = $('#new_password').val();
                if (new_pw !== '') {
                    var password_ok = password_quality(new_pw);
                    if (password_ok === undefined) {
                        // zxcvbn.js didn't load, for whatever reason.
                        settings_change_error(
                            'An internal error occurred; try reloading the page. ' +
                            'Sorry for the trouble!');
                        return false;
                    } else if (!password_ok) {
                        settings_change_error('New password is too weak');
                        return false;
                    }
                }
            }
            return true;
        },
        success: function () {
            settings_change_success("Updated settings!");
        },
        error: function (xhr) {
            settings_change_error("Error changing settings", xhr);
        },
        complete: function () {
            // Whether successful or not, clear the password boxes.
            // TODO: Clear these earlier, while the request is still pending.
            clear_password_change();
        }
    });

    function update_notification_settings_success(resp, statusText, xhr) {
        var result = JSON.parse(xhr.responseText);
        var notify_settings_status = $('#notify-settings-status').expectOne();

        // Stream notification settings.

        if (result.enable_stream_desktop_notifications !== undefined) {
            page_params.stream_desktop_notifications_enabled =
                result.enable_stream_desktop_notifications;
        }
        if (result.enable_stream_sounds !== undefined) {
            page_params.stream_sounds_enabled = result.enable_stream_sounds;
        }

        // PM and @-mention notification settings.

        if (result.enable_desktop_notifications !== undefined) {
            page_params.desktop_notifications_enabled = result.enable_desktop_notifications;
        }
        if (result.enable_sounds !== undefined) {
            page_params.sounds_enabled = result.enable_sounds;
        }

        if (result.enable_offline_email_notifications !== undefined) {
            page_params.enable_offline_email_notifications =
                result.enable_offline_email_notifications;
        }

        if (result.enable_offline_push_notifications !== undefined) {
            page_params.enable_offline_push_notifications =
                result.enable_offline_push_notifications;
        }

        if (result.enable_online_push_notifications !== undefined) {
            page_params.enable_online_push_notifications = result.enable_online_push_notifications;
        }

        if (result.pm_content_in_desktop_notifications !== undefined) {
            page_params.pm_content_in_desktop_notifications
                = result.pm_content_in_desktop_notifications;
        }
        // Other notification settings.

        if (result.enable_digest_emails !== undefined) {
            page_params.enable_digest_emails = result.enable_digest_emails;
        }

        ui.report_success(i18n.t("Updated notification settings!"), notify_settings_status);
    }

    function update_notification_settings_error(xhr) {
        ui.report_error(i18n.t("Error changing settings"), xhr, $('#notify-settings-status').expectOne());
    }

    function post_notify_settings_changes(notification_changes, success_func,
                                          error_func) {
        return channel.patch({
            url: "/json/settings/notifications",
            data: notification_changes,
            success: success_func,
            error: error_func
        });
    }

    $("#change_notification_settings").on("click", function (e) {
        e.preventDefault();

        var updated_settings = {};
        _.each(["enable_stream_desktop_notifications", "enable_stream_sounds",
                "enable_desktop_notifications", "pm_content_in_desktop_notifications", "enable_sounds",
                "enable_offline_email_notifications",
                "enable_offline_push_notifications", "enable_online_push_notifications",
                "enable_digest_emails"],
               function (setting) {
                   updated_settings[setting] = $("#" + setting).is(":checked");
               });
        post_notify_settings_changes(updated_settings,
                                     update_notification_settings_success,
                                     update_notification_settings_error);
    });

    function update_global_stream_setting(notification_type, new_setting) {
        var data = {};
        data[notification_type] = new_setting;
        channel.patch({
            url: "/json/settings/notifications",
            data: data,
            success: update_notification_settings_success,
            error: update_notification_settings_error
        });
    }

    function update_desktop_notification_setting(new_setting) {
        update_global_stream_setting("enable_stream_desktop_notifications", new_setting);
        subs.set_all_stream_desktop_notifications_to(new_setting);
    }

    function update_audible_notification_setting(new_setting) {
        update_global_stream_setting("enable_stream_sounds", new_setting);
        subs.set_all_stream_audible_notifications_to(new_setting);
    }

    function maybe_bulk_update_stream_notification_setting(notification_checkbox,
                                                           propagate_setting_function) {
        var html = templates.render("propagate_notification_change");
        var control_group = notification_checkbox.closest(".control-group");
        var checkbox_status = notification_checkbox.is(":checked");
        control_group.find(".propagate_stream_notifications_change").html(html);
        control_group.find(".yes_propagate_notifications").on("click", function () {
            propagate_setting_function(checkbox_status);
            control_group.find(".propagate_stream_notifications_change").empty();
        });
        control_group.find(".no_propagate_notifications").on("click", function () {
            control_group.find(".propagate_stream_notifications_change").empty();
        });
    }

    $("#enable_stream_desktop_notifications").on("click", function () {
        var notification_checkbox = $("#enable_stream_desktop_notifications");
        maybe_bulk_update_stream_notification_setting(notification_checkbox,
                                                      update_desktop_notification_setting);
    });

    $("#enable_stream_sounds").on("click", function () {
        var notification_checkbox = $("#enable_stream_sounds");
        maybe_bulk_update_stream_notification_setting(notification_checkbox,
                                                      update_audible_notification_setting);
    });

    $("#left_side_userlist").change(function () {
        var left_side_userlist = this.checked;
        var data = {};
        data.left_side_userlist = JSON.stringify(left_side_userlist);
        var context = {};
        if (data.left_side_userlist === "true") {
            context.side = i18n.t('left');
        } else {
            context.side = i18n.t('right');
        }

        channel.patch({
            url: '/json/settings/display',
            data: data,
            success: function () {
                ui.report_success(i18n.t("User list will appear on the __side__ hand side! You will need to reload the window for your changes to take effect.", context),
                                  $('#display-settings-status').expectOne());
            },
            error: function (xhr) {
                ui.report_error(i18n.t("Error updating user list placement setting"), xhr, $('#display-settings-status').expectOne());
            }
        });
    });

    $("#twenty_four_hour_time").change(function () {
        var data = {};
        var setting_value = $("#twenty_four_hour_time").is(":checked");
        data.twenty_four_hour_time = JSON.stringify(setting_value);
        var context = {};
        if (data.twenty_four_hour_time === "true") {
            context.format = '24';
        } else {
            context.format = '12';
        }

        channel.patch({
            url: '/json/settings/display',
            data: data,
            success: function () {
                ui.report_success(i18n.t("Time will be displayed in the __format__-hour format!  You will need to reload the window for your changes to take effect", context),
                                  $('#display-settings-status').expectOne());
            },
            error: function (xhr) {
                ui.report_error(i18n.t("Error updating time format setting"), xhr, $('#display-settings-status').expectOne());
            }
        });
    });

    $("#default_language_modal .language").click(function (e) {
        e.preventDefault();
        e.stopPropagation();
        $('#default_language_modal').modal('hide');

        var data = {};
        var $link = $(e.target).closest("a[data-code]");
        var setting_value = $link.attr('data-code');
        data.default_language = JSON.stringify(setting_value);

        var new_language = $link.attr('data-name');
        $('#default_language_name').text(new_language);

        var context = {};
        context.lang = new_language;

        channel.patch({
            url: '/json/settings/display',
            data: data,
            success: function () {
                ui.report_success(i18n.t("__lang__ is now the default language!  You will need to reload the window for your changes to take effect", context),
                                  $('#display-settings-status').expectOne());
            },
            error: function (xhr) {
                ui.report_error(i18n.t("Error updating default language setting"), xhr, $('#display-settings-status').expectOne());
            }
        });
    });

    $('#default_language').on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        $('#default_language_modal').modal('show');
    });

    $("#user_deactivate_account_button").on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        $("#deactivate_self_modal").modal("show");
    });

    $("#do_deactivate_self_button").on('click',function () {
        $("#deactivate_self_modal").modal("hide");
        channel.del({
            url: '/json/users/me',
            success: function () {
                window.location.href = "/login";
            },
            error: function (xhr) {
                ui.report_error(i18n.t("Error deactivating account"), xhr, $('#settings-status').expectOne());
            }
        });
    });

    $("#get_api_key_box").hide();
    $("#show_api_key_box").hide();
    $("#get_api_key_box form").ajaxForm({
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        success: function (resp, statusText, xhr) {
            var result = JSON.parse(xhr.responseText);
            var settings_status = $('#settings-status').expectOne();

            $("#get_api_key_password").val("");
            $("#api_key_value").text(result.api_key);
            $("#show_api_key_box").show();
            $("#get_api_key_box").hide();
            settings_status.hide();
        },
        error: function (xhr) {
            ui.report_error(i18n.t("Error getting API key"), xhr, $('#settings-status').expectOne());
            $("#show_api_key_box").hide();
            $("#get_api_key_box").show();
        }
    });

    function upload_avatar(file_input) {
        var form_data = new FormData();

        form_data.append('csrfmiddlewaretoken', csrf_token);
        jQuery.each(file_input[0].files, function (i, file) {
            form_data.append('file-'+i, file);
        });

        var spinner = $("#upload_avatar_spinner").expectOne();
        loading.make_indicator(spinner, {text: 'Uploading avatar.'});

        channel.put({
            url: '/json/users/me/avatar',
            data: form_data,
            cache: false,
            processData: false,
            contentType: false,
            success: function (data) {
                loading.destroy_indicator($("#upload_avatar_spinner"));
                var url = data.avatar_url + '&stamp=' + exports.avatar_stamp;
                $("#user-settings-avatar").expectOne().attr("src", url);
                $("#user_avatar_delete_button").show();
                exports.avatar_stamp += 1;
            }
        });

    }

    avatar.build_user_avatar_widget(upload_avatar);

    if (page_params.name_changes_disabled) {
        $(".name_change_container").hide();
    }


    // TODO: render bots xxxx
    render_bots();
    $(document).on('zulip.bot_data_changed', render_bots);

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
            var short_name = $('#create_bot_short_name').val() || $('#create_bot_short_name').text();
            var default_sending_stream = $('#create_bot_default_sending_stream').val();
            var default_events_register_stream = $('#create_bot_default_events_register_stream').val();
            var formData = new FormData();

            formData.append('csrfmiddlewaretoken', csrf_token);
            formData.append('full_name', full_name);
            formData.append('short_name', short_name);
            add_bot_default_streams_to_form(formData, default_sending_stream,
                                            default_events_register_stream);
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
                success: function () {
                    $('#bot_table_error').hide();
                    $('#create_bot_name').val('');
                    $('#create_bot_short_name').val('');
                    $('#create_bot_button').show();
                    create_avatar_widget.clear();
                },
                error: function (xhr) {
                    $('#bot_table_error').text(JSON.parse(xhr.responseText).msg).show();
                },
                complete: function () {
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
            success: function () {
                errors.hide();
            },
            submitHandler: function () {
                var email = form.data('email');
                var full_name = form.find('.edit_bot_name').val();
                var file_input = li.find('.edit_bot_avatar_file_input');
                var default_sending_stream = form.find('.edit_bot_default_sending_stream').val();
                var default_events_register_stream = form.find('.edit_bot_default_events_register_stream').val();
                var spinner = form.find('.edit_bot_spinner');
                var edit_button = form.find('.edit_bot_button');
                var formData = new FormData();

                formData.append('csrfmiddlewaretoken', csrf_token);
                formData.append('full_name', full_name);
                add_bot_default_streams_to_form(formData, default_sending_stream,
                                                default_events_register_stream);
                jQuery.each(file_input[0].files, function (i, file) {
                    formData.append('file-'+i, file);
                });
                loading.make_indicator(spinner, {text: 'Editing bot'});
                edit_button.hide();
                channel.patch({
                    url: '/json/bots/' + encodeURIComponent(email),
                    data: formData,
                    cache: false,
                    processData: false,
                    contentType: false,
                    success: function (data) {
                        loading.destroy_indicator(spinner);
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
                    error: function (xhr) {
                        loading.destroy_indicator(spinner);
                        edit_button.show();
                        errors.text(JSON.parse(xhr.responseText).msg).show();
                    }
                });
            }
        });


    });

    $("#bots_list").on("click", "a.download_bot_zuliprc", function () {
        var bot_info = $(this).parent().parent();
        var email = bot_info.find(".email .value").text();
        var api_key = bot_info.find(".api_key .api-key-value-and-button .value").text();

        $(this).attr("href", settings.generate_zuliprc_uri(
            $.trim(email), $.trim(api_key)
        ));
    });

    $("#download_zuliprc").on("click", function () {
        $(this).attr("href", settings.generate_zuliprc_uri(
            page_params.email,
            $("#api_key_value").text()
        ));
    });

    $("#show_api_key_box").on("click", "button.regenerate_api_key", function () {
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

    $("#ui-settings").on("click", "input[name='change_settings']", function (e) {
        e.preventDefault();
        var labs_updates = {};
        _.each(["autoscroll_forever", "default_desktop_notifications"],
            function (setting) {
                labs_updates[setting] = $("#" + setting).is(":checked");
        });

        channel.patch({
            url: '/json/settings/ui',
            data: labs_updates,
            success: function (resp, statusText, xhr) {
                var message = i18n.t("Updated __product_name__ Labs settings!  You will need to reload for these changes to take effect.", page_params);
                var result = JSON.parse(xhr.responseText);
                var ui_settings_status = $('#ui-settings-status').expectOne();

                if (result.autoscroll_forever !== undefined) {
                    page_params.autoscroll_forever = result.autoscroll_forever;
                    resize.resize_page_components();
                }

                ui.report_success(message, ui_settings_status);
            },
            error: function (xhr) {
                ui.report_error(i18n.t("Error changing settings"), xhr, $('#ui-settings-status').expectOne());
            }
        });
    });
}

function _update_page() {
    $("#twenty_four_hour_time").prop('checked', page_params.twenty_four_hour_time);
    $("#left_side_userlist").prop('checked', page_params.left_side_userlist);
    $("#default_language_name").text(page_params.default_language_name);

    $("#enable_stream_desktop_notifications").prop('checked', page_params.stream_desktop_notifications_enabled);
    $("#enable_stream_sounds").prop('checked', page_params.stream_sounds_enabled);
    $("#enable_desktop_notifications").prop('checked', page_params.desktop_notifications_enabled);
    $("#enable_sounds").prop('checked', page_params.sounds_enabled);
    $("#enable_offline_email_notifications").prop('checked', page_params.enable_offline_email_notifications);
    $("#enable_offline_push_notifications").prop('checked', page_params.enable_offline_push_notifications);
    $("#enable_online_push_notifications").prop('checked', page_params.enable_online_push_notifications);
    $("#pm_content_in_desktop_notifications").prop('checked', page_params.pm_content_in_desktop_notifications);
    $("#enable_digest_emails").prop('checked', page_params.enable_digest_emails);
}

exports.setup_page = function () {
    i18n.ensure_i18n(_setup_page);
};

exports.update_page = function () {
    i18n.ensure_i18n(_update_page);
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings;
}
