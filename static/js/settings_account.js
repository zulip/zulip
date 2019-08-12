var render_settings_custom_user_profile_field = require("../templates/settings/custom_user_profile_field.hbs");
var render_settings_dev_env_email_access = require('../templates/settings/dev_env_email_access.hbs');
var render_settings_api_key_modal = require('../templates/settings/api_key_modal.hbs');

var settings_account = (function () {

var exports = {};

exports.update_email = function (new_email) {
    var email_input = $('#email_value');

    if (email_input) {
        email_input.text(new_email);
    }
};

exports.update_full_name = function (new_full_name) {
    var full_name_field = $("#change_full_name button #full_name_value");
    if (full_name_field) {
        full_name_field.text(new_full_name);
    }

    // Arguably, this should work more like how the `update_email`
    // flow works, where we update the name in the modal on open,
    // rather than updating it here, but this works.
    var full_name_input = $(".full_name_change_container input[name='full_name']");
    if (full_name_input) {
        full_name_input.val(new_full_name);
    }
};

exports.user_can_change_name = function () {
    if (page_params.is_admin) {
        return true;
    }
    if (page_params.realm_name_changes_disabled || page_params.server_name_changes_disabled) {
        return false;
    }
    return true;
};

exports.update_name_change_display = function () {
    if (!exports.user_can_change_name()) {
        $('#full_name').attr('disabled', 'disabled');
        $(".change_name_tooltip").show();
    } else {
        $('#full_name').attr('disabled', false);
        $(".change_name_tooltip").hide();
    }
};

exports.update_email_change_display = function () {
    if (page_params.realm_email_changes_disabled && !page_params.is_admin) {
        $('#change_email .button').attr('disabled', 'disabled');
        $(".change_email_tooltip").show();
    } else {
        $('#change_email .button').attr('disabled', false);
        $(".change_email_tooltip").hide();
    }
};

exports.update_avatar_change_display = function () {
    if ((page_params.realm_avatar_changes_disabled ||
         page_params.server_avatar_changes_disabled)
            && !page_params.is_admin) {
        $('#user_avatar_upload_button .button').attr('disabled', 'disabled');
        $('#user_avatar_delete_button .button').attr('disabled', 'disabled');
    } else {
        $('#user_avatar_upload_button .button').attr('disabled', false);
        $('#user_avatar_delete_button .button').attr('disabled', false);
    }
};

function settings_change_error(message, xhr) {
    ui_report.error(message, xhr, $('#account-settings-status').expectOne());
}

function update_custom_profile_field(field, method) {
    var field_id;
    if (method === channel.del) {
        field_id = field;
    } else {
        field_id = field.id;
    }

    var spinner = $('.custom_user_field[data-field-id="' + field_id +
        '"] .custom-field-status').expectOne();
    loading.make_indicator(spinner, {text: 'Saving ...'});
    settings_ui.do_settings_change(method, "/json/users/me/profile_data",
                                   {data: JSON.stringify([field])}, spinner);
}

function update_user_custom_profile_fields(fields, method) {
    if (method === undefined) {
        blueslip.error("Undefined method in update_user_custom_profile_fields");
    }
    _.each(fields, function (field) {
        update_custom_profile_field(field, method);
    });
}

exports.append_custom_profile_fields = function (element_id, user_id) {
    var person = people.get_person_from_user_id(user_id);
    if (person.is_bot) {
        return;
    }
    var all_custom_fields = page_params.custom_profile_fields;
    var all_field_types = page_params.custom_profile_field_types;

    var all_field_template_types = {};
    all_field_template_types[all_field_types.LONG_TEXT.id] = "text";
    all_field_template_types[all_field_types.SHORT_TEXT.id] = "text";
    all_field_template_types[all_field_types.CHOICE.id] = "choice";
    all_field_template_types[all_field_types.USER.id] = "user";
    all_field_template_types[all_field_types.DATE.id] = "date";
    all_field_template_types[all_field_types.EXTERNAL_ACCOUNT.id] = "text";
    all_field_template_types[all_field_types.URL.id] = "url";

    all_custom_fields.forEach(function (field) {
        var field_value = people.get_custom_profile_data(user_id, field.id);
        var is_choice_field = field.type === all_field_types.CHOICE.id;
        var field_choices = [];

        if (field_value === undefined || field_value === null) {
            field_value = {value: "", rendered_value: ""};
        }
        if (is_choice_field) {
            var field_choice_dict = JSON.parse(field.field_data);
            for (var choice in field_choice_dict) {
                if (choice) {
                    field_choices[field_choice_dict[choice].order] = {
                        value: choice,
                        text: field_choice_dict[choice].text,
                        selected: choice === field_value.value,
                    };
                }
            }
        }

        var html = render_settings_custom_user_profile_field({
            field: field,
            field_type: all_field_template_types[field.type],
            field_value: field_value,
            is_long_text_field: field.type === all_field_types.LONG_TEXT.id,
            is_user_field: field.type === all_field_types.USER.id,
            is_date_field: field.type === all_field_types.DATE.id,
            is_choice_field: is_choice_field,
            field_choices: field_choices,
        });
        $(element_id).append(html);
    });
};

exports.initialize_custom_date_type_fields = function (element_id) {
    $(element_id).find(".custom_user_field .datepicker").flatpickr({
        altInput: true,
        altFormat: "F j, Y"});

    $(element_id).find(".custom_user_field .datepicker").on("mouseenter", function () {
        if ($(this).val().length <= 0) {
            $(this).parent().find(".remove_date").hide();
        } else {
            $(this).parent().find(".remove_date").show();
        }
    });

    $(element_id).find(".custom_user_field .remove_date").on("click", function () {
        $(this).parent().find(".custom_user_field_value").val("");
    });
};

exports.initialize_custom_user_type_fields = function (element_id, user_id, is_editable,
                                                       set_handler_on_update) {
    var field_types = page_params.custom_profile_field_types;
    var user_pills = {};

    var person = people.get_person_from_user_id(user_id);
    if (person.is_bot) {
        return [];
    }

    page_params.custom_profile_fields.forEach(function (field) {
        var field_value_raw = people.get_custom_profile_data(user_id, field.id);

        if (field_value_raw) {
            field_value_raw = field_value_raw.value;
        }

        // If field is not editable and field value is null, we don't expect
        // pill container for that field and proceed further
        if (field.type === field_types.USER.id && (field_value_raw || is_editable)) {
            var pill_container = $(element_id).find('.custom_user_field[data-field-id="' +
                                         field.id + '"] .pill-container').expectOne();
            var pills = user_pill.create_pills(pill_container);

            function update_custom_user_field() {
                var fields = [];
                var user_ids = user_pill.get_user_ids(pills);
                if (user_ids.length < 1) {
                    fields.push(field.id);
                    update_user_custom_profile_fields(fields, channel.del);
                } else {
                    fields.push({id: field.id, value: user_ids});
                    update_user_custom_profile_fields(fields, channel.patch);
                }
            }

            if (field_value_raw) {
                var field_value = JSON.parse(field_value_raw);
                if (field_value) {
                    field_value.forEach(function (pill_user_id) {
                        var user = people.get_person_from_user_id(pill_user_id);
                        user_pill.append_user(user, pills);
                    });
                }
            }

            if (is_editable) {
                var input = pill_container.children('.input');
                if (set_handler_on_update) {
                    user_pill.set_up_typeahead_on_pills(input, pills, update_custom_user_field);
                    pills.onPillRemove(function () {
                        update_custom_user_field();
                    });
                } else {
                    user_pill.set_up_typeahead_on_pills(input, pills, function () {});
                }
            }
            user_pills[field.id] = pills;
        }
    });

    return user_pills;
};

exports.add_custom_profile_fields_to_settings = function () {
    if (!overlays.settings_open()) {
        return;
    }

    var element_id = "#account-settings .custom-profile-fields-form";
    $(element_id).html("");
    if (page_params.custom_profile_fields.length > 0) {
        $("#account-settings #custom-field-header").show();
    } else {
        $("#account-settings #custom-field-header").hide();
    }

    exports.append_custom_profile_fields(element_id, people.my_current_user_id());
    exports.initialize_custom_user_type_fields(element_id, people.my_current_user_id(), true, true);
    exports.initialize_custom_date_type_fields(element_id);
};

exports.set_up = function () {
    // Add custom profile fields elements to user account settings.
    exports.add_custom_profile_fields_to_settings();
    $("#account-settings-status").hide();

    var setup_api_key_modal = _.once(function () {
        $('.account-settings-form').append(render_settings_api_key_modal());
        $("#api_key_value").text("");
        $("#show_api_key").hide();

        if (page_params.realm_password_auth_enabled === false) {
            // Skip the password prompt step, since the user doesn't have one.
            $("#get_api_key_button").click();
        }

        $("#get_api_key_button").on("click", function (e) {
            var data = {};
            e.preventDefault();
            e.stopPropagation();

            data.password = $("#get_api_key_password").val();
            channel.post({
                url: '/json/fetch_api_key',
                data: data,
                success: function (data) {
                    $("#get_api_key_password").val("");
                    $("#api_key_value").text(data.api_key);
                    // The display property on the error bar is set to important
                    // so instead of making display: none !important we just
                    // remove it.
                    $('#api_key_status').remove();
                    $("#password_confirmation").hide();
                    $("#show_api_key").show();
                },
                error: function (xhr) {
                    ui_report.error(i18n.t("Error"), xhr, $('#api_key_status').expectOne());
                    $("#show_api_key").hide();
                    $("#api_key_modal").show();
                },
            });
        });

        $("#show_api_key").on("click", "button.regenerate_api_key", function (e) {
            channel.post({
                url: '/json/users/me/api_key/regenerate',
                success: function (data) {
                    $('#api_key_value').text(data.api_key);
                },
                error: function (xhr) {
                    $('#user_api_key_error').text(JSON.parse(xhr.responseText).msg).show();
                },
            });
            e.preventDefault();
            e.stopPropagation();
        });

        $("#download_zuliprc").on("click", function () {
            var data = settings_bots.generate_zuliprc_content(people.my_current_email(),
                                                              $("#api_key_value").text());
            $(this).attr("href", settings_bots.encode_zuliprc_as_uri(data));
        });
    });

    $('#api_key_button').click(function (e) {
        setup_api_key_modal();
        overlays.open_modal('api_key_modal');
        e.preventDefault();
        e.stopPropagation();
    });

    function clear_password_change() {
        // Clear the password boxes so that passwords don't linger in the DOM
        // for an XSS attacker to find.
        $('#old_password, #new_password').val('');
        common.password_quality('', $('#pw_strength .bar'), $('#new_password'));
    }

    clear_password_change();

    $("#change_full_name").on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        if (exports.user_can_change_name()) {
            $('#change_full_name_modal').find("input[name='full_name']").val(page_params.full_name);
            overlays.open_modal('change_full_name_modal');
        }
    });

    $('#change_password').on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        overlays.open_modal('change_password_modal');
        $('#pw_change_controls').show();
        if (page_params.realm_password_auth_enabled !== false) {
            // zxcvbn.js is pretty big, and is only needed on password
            // change, so load it asynchronously.
            require(['zxcvbn'], function (zxcvbn) {
                window.zxcvbn = zxcvbn;
                $('#pw_strength .bar').removeClass("fade");
            });
        }
    });

    $('#change_password_modal').find('[data-dismiss=modal]').on('click', function () {
        clear_password_change();
    });

    // If the modal is closed using the 'close' button or the 'Cancel' button
    $('.modal').find('[data-dismiss=modal]').on('click', function () {
        // Enable mouse events for the background on closing modal
        $('.overlay.show').attr("style", null);
    });

    $('#change_password_button').on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var change_password_error = $('#change_password_modal').find(".change_password_info").expectOne();

        var data = {
            old_password: $('#old_password').val(),
            new_password: $('#new_password').val(),
            confirm_password: $('#confirm_password').val(),
        };

        var new_pw_field = $('#new_password');
        var new_pw = data.new_password;
        if (new_pw !== '') {
            var password_ok = common.password_quality(new_pw, undefined, new_pw_field);
            if (password_ok === undefined) {
                // zxcvbn.js didn't load, for whatever reason.
                settings_change_error(
                    'An internal error occurred; try reloading the page. ' +
                        'Sorry for the trouble!');
                return;
            } else if (!password_ok) {
                settings_change_error(i18n.t('New password is too weak'));
                return;
            }
        }

        var opts = {
            success_continuation: function () {
                overlays.close_modal("change_password_modal");
            },
            error_msg_element: change_password_error,
        };
        settings_ui.do_settings_change(channel.patch, '/json/settings', data,
                                       $('#account-settings-status').expectOne(), opts);
        clear_password_change();
    });

    $('#new_password').on('input', function () {
        var field = $('#new_password');
        common.password_quality(field.val(), $('#pw_strength .bar'), field);
    });

    $("#change_full_name_button").on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var change_full_name_error = $('#change_full_name_modal').find(".change_full_name_info").expectOne();
        var data = {};

        data.full_name = $('.full_name_change_container').find("input[name='full_name']").val();

        var opts = {
            success_continuation: function () {
                overlays.close_modal("change_full_name_modal");
            },
            error_msg_element: change_full_name_error,
        };
        settings_ui.do_settings_change(channel.patch, '/json/settings', data,
                                       $('#account-settings-status').expectOne(), opts);
    });

    $('#change_email_button').on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var change_email_error = $('#change_email_modal').find(".change_email_info").expectOne();
        var data = {};
        data.email = $('.email_change_container').find("input[name='email']").val();

        var opts = {
            success_continuation: function () {
                if (page_params.development_environment) {
                    var email_msg = render_settings_dev_env_email_access();
                    ui_report.success(email_msg, $("#dev-account-settings-status").expectOne(), 4000);
                }
                overlays.close_modal('change_email_modal');
            },
            error_msg_element: change_email_error,
            success_msg: i18n.t('Check your email (%s) to confirm the new address.').replace(
                "%s", data.email),
        };
        settings_ui.do_settings_change(channel.patch, '/json/settings', data,
                                       $('#account-settings-status').expectOne(), opts);
    });

    $('#change_email').on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        if (!page_params.realm_email_changes_disabled || page_params.is_admin) {
            overlays.open_modal('change_email_modal');
            var email = $('#email_value').text().trim();
            $('.email_change_container').find("input[name='email']").val(email);
        }
    });

    $("#user_deactivate_account_button").on('click', function (e) {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active_modal` in `settings.js`.
        e.preventDefault();
        e.stopPropagation();
        $("#deactivate_self_modal").modal("show");
    });

    $('#account-settings').on('click', '.custom_user_field .remove_date', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var field = $(e.target).closest('.custom_user_field').expectOne();
        var field_id = parseInt($(field).attr("data-field-id"), 10);
        update_user_custom_profile_fields([field_id], channel.del);
    });

    $('#account-settings').on('change', '.custom_user_field_value', function (e) {
        var fields = [];
        var value = $(this).val();
        var field_id = parseInt($(e.target).closest('.custom_user_field').attr("data-field-id"), 10);
        if (value) {
            fields.push({id: field_id, value: value});
            update_user_custom_profile_fields(fields, channel.patch);
        } else {
            fields.push(field_id);
            update_user_custom_profile_fields(fields, channel.del);
        }
    });

    $("#do_deactivate_self_button").on('click', function () {
        $("#do_deactivate_self_button .loader").css('display', 'inline-block');
        $("#do_deactivate_self_button span").hide();
        $("#do_deactivate_self_button object").on("load", function () {
            var doc = this.getSVGDocument();
            var $svg = $(doc).find("svg");
            $svg.find("rect").css("fill", "#000");
        });

        setTimeout(function () {
            channel.del({
                url: '/json/users/me',
                success: function () {
                    $("#deactivate_self_modal").modal("hide");
                    window.location.href = "/login/";
                },
                error: function (xhr) {
                    var error_last_admin = i18n.t("Error: Cannot deactivate the only organization administrator.");
                    var error_last_user = i18n.t("Error: Cannot deactivate the only user. You can deactivate the whole organization though in your <a target=\"_blank\" href=\"/#organization/organization-profile\">Organization profile settings</a>.");
                    var rendered_error_msg;
                    if (xhr.responseJSON.code === "CANNOT_DEACTIVATE_LAST_USER") {
                        if (xhr.responseJSON.is_last_admin) {
                            rendered_error_msg = error_last_admin;
                        } else {
                            rendered_error_msg = error_last_user;
                        }
                    }
                    $("#deactivate_self_modal").modal("hide");
                    $("#account-settings-status").addClass("alert-error").html(rendered_error_msg).show();
                },
            });
        }, 5000);
    });

    $("#show_my_user_profile_modal").on('click', function () {
        overlays.close_overlay("settings");
        var user = people.get_person_from_user_id(people.my_current_user_id());
        setTimeout(function () {
            popovers.show_user_profile(user);
        }, 100);

        // If user opened the "preview profile" modal from user
        // settings, then closing preview profile modal should
        // send them back to the settings modal.
        $('body').one('hidden.bs.modal', '#user-profile-modal', function (e) {
            e.preventDefault();
            e.stopPropagation();
            popovers.hide_user_profile();

            setTimeout(function () {
                if (!overlays.settings_open()) {
                    overlays.open_settings();
                }
            }, 100);
        });
    });


    function upload_avatar(file_input) {
        var form_data = new FormData();

        form_data.append('csrfmiddlewaretoken', csrf_token);
        jQuery.each(file_input[0].files, function (i, file) {
            form_data.append('file-' + i, file);
        });

        $("#user-avatar-source").hide();

        var spinner = $("#upload_avatar_spinner").expectOne();
        loading.make_indicator(spinner, {text: i18n.t('Uploading profile picture.')});

        channel.post({
            url: '/json/users/me/avatar',
            data: form_data,
            cache: false,
            processData: false,
            contentType: false,
            success: function () {
                loading.destroy_indicator($("#upload_avatar_spinner"));
                $("#user_avatar_delete_button").show();
                $("#user_avatar_file_input_error").hide();
                $("#user-avatar-source").hide();
                // Rest of the work is done via the user_events -> avatar_url event we will get
            },
            error: function (xhr) {
                loading.destroy_indicator($("#upload_avatar_spinner"));
                if (page_params.avatar_source === 'G') {
                    $("#user-avatar-source").show();
                }
                var $error = $("#user_avatar_file_input_error");
                $error.text(JSON.parse(xhr.responseText).msg);
                $error.show();
            },
        });

    }

    avatar.build_user_avatar_widget(upload_avatar);

    if (page_params.realm_name_changes_disabled) {
        $(".name_change_container").hide();
    }

};


return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_account;
}
window.settings_account = settings_account;
