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

exports.update_name_change_display = function () {
    if (page_params.realm_name_changes_disabled && !page_params.is_admin) {
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

function settings_change_error(message, xhr) {
    ui_report.error(message, xhr, $('#account-settings-status').expectOne());
}

function settings_change_success(message) {
    ui_report.success(message, $('#account-settings-status').expectOne());
}

function update_user_custom_profile_fields(fields, method) {
    if (method === undefined) {
        blueslip.error("Undefined method in update_user_custom_profile_fields");
    }
    var spinner = $("#custom-field-status").expectOne();
    loading.make_indicator(spinner, {text: 'Saving ...'});
    settings_ui.do_settings_change(method, "/json/users/me/profile_data",
                                   {data: JSON.stringify(fields)}, spinner);
}

exports.append_custom_profile_fields = function (element_id, user_id) {
    var all_custom_fields = page_params.custom_profile_fields;
    var field_types = page_params.custom_profile_field_types;

    all_custom_fields.forEach(function (field) {
        var field_type = field.type;
        var type;
        var field_value = people.get_custom_profile_data(user_id, field.id);
        if (field_value === undefined || field_value === null) {
            field_value = {value: "", rendered_value: ""};
        }
        var is_long_text = field_type === field_types.LONG_TEXT.id;
        var is_choice_field = field_type === field_types.CHOICE.id;
        var is_user_field = field_type === field_types.USER.id;
        var is_date_field = field_type === field_types.DATE.id;
        var field_choices = [];

        if (is_long_text || field_type === field_types.SHORT_TEXT.id) {
            type = "text";
        } else if (is_choice_field) {
            type = "choice";
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
        } else if (is_date_field) {
            type = "date";
        } else if (field_type === field_types.URL.id) {
            type = "url";
        } else if (is_user_field) {
            type = "user";
        } else {
            blueslip.error("Undefined field type.");
        }

        var html = templates.render("custom-user-profile-field", {
            field: field,
            field_type: type,
            field_value: field_value,
            is_long_text_field: is_long_text,
            is_choice_field: is_choice_field,
            is_user_field: is_user_field,
            is_date_field: is_date_field,
            field_choices: field_choices,
        });
        $(element_id).append(html);
    });
};

exports.initialize_custom_date_type_fields = function (element_id) {
    $(element_id).find(".custom_user_field .datepicker").flatpickr({
        altInput: true,
        altFormat: "F j, Y"});
};

exports.intialize_custom_user_type_fields = function (element_id, user_id, is_editable,
                                                      set_handler_on_update) {
    var field_types = page_params.custom_profile_field_types;
    var user_pills = {};

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
    exports.intialize_custom_user_type_fields(element_id, people.my_current_user_id(), true, true);
    exports.initialize_custom_date_type_fields(element_id);
};

exports.set_up = function () {
    // Add custom profile fields elements to user account settings.
    exports.add_custom_profile_fields_to_settings();
    $("#account-settings-status").hide();
    $("#api_key_value").text("");
    $("#get_api_key_box").hide();
    $("#show_api_key_box").hide();
    $("#api_key_button_box").show();

    $('#api_key_button').click(function () {
        if (page_params.realm_password_auth_enabled !== false) {
            $("#get_api_key_box").show();
        } else {
            // Skip the password prompt step
            $("#get_api_key_box form").submit();
        }
        $("#api_key_button_box").hide();
    });

    $("#get_api_key_box").hide();
    $("#show_api_key_box").hide();

    $("#get_api_key_button").on("click", function (e) {
        var data = {};
        e.preventDefault();
        e.stopPropagation();

        data.password = $("#get_api_key_password").val();
        channel.post({
            url: '/json/fetch_api_key',
            dataType: 'json',
            data: data,
            success: function (data) {
                var settings_status = $('#account-settings-status').expectOne();

                $("#get_api_key_password").val("");
                $("#api_key_value").text(data.api_key);
                $("#show_api_key_box").show();
                $("#get_api_key_box").hide();
                settings_status.hide();
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Error getting API key"), xhr, $('#account-settings-status').expectOne());
                $("#show_api_key_box").hide();
                $("#get_api_key_box").show();
            },
        });
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
            },
        });
    });

    $("#download_zuliprc").on("click", function () {
        var data = settings_bots.generate_zuliprc_content(people.my_current_email(),
                                                          $("#api_key_value").text());
        $(this).attr("href", settings_bots.encode_zuliprc_as_uri(data));
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
        if (!page_params.realm_name_changes_disabled || page_params.is_admin) {
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
            var zxcvbn_path = '/static/min/zxcvbn.js';
            if (page_params.development_environment) {
                // Usually the Django templates handle this path stuff
                // for us, but in this case we need to hardcode it.
                zxcvbn_path = '/static/node_modules/zxcvbn/dist/zxcvbn.js';
            }
            $.getScript(zxcvbn_path, function () {
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
        var change_password_info = $('#change_password_modal').find(".change_password_info").expectOne();

        var data = {
            old_password: $('#old_password').val(),
            new_password: $('#new_password').val(),
            confirm_password: $('#confirm_password').val(),
        };

        channel.patch({
            url: "/json/settings",
            data: data,
            beforeSend: function () {
                if (page_params.realm_password_auth_enabled !== false) {
                    // FIXME: Check that the two password fields match
                    // FIXME: Use the same jQuery validation plugin as the signup form?
                    var field = $('#new_password');
                    var new_pw = $('#new_password').val();
                    if (new_pw !== '') {
                        var password_ok = common.password_quality(new_pw, undefined, field);
                        if (password_ok === undefined) {
                            // zxcvbn.js didn't load, for whatever reason.
                            settings_change_error(
                                'An internal error occurred; try reloading the page. ' +
                                'Sorry for the trouble!');
                            return false;
                        } else if (!password_ok) {
                            settings_change_error(i18n.t('New password is too weak'));
                            return false;
                        }
                    }
                }
                return true;
            },
            success: function () {
                settings_change_success(i18n.t("Updated settings!"));
                overlays.close_modal('change_password_modal');
            },
            complete: function () {
                // Whether successful or not, clear the password boxes.
                // TODO: Clear these earlier, while the request is still pending.
                clear_password_change();
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Failed"), xhr, change_password_info);
            },
        });
    });

    $('#new_password').on('change keyup', function () {
        var field = $('#new_password');
        common.password_quality(field.val(), $('#pw_strength .bar'), field);
    });

    $("#change_full_name_button").on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var change_full_name_info = $('#change_full_name_modal').find(".change_full_name_info").expectOne();
        var data = {};

        data.full_name = $('.full_name_change_container').find("input[name='full_name']").val();
        channel.patch({
            url: '/json/settings',
            data: data,
            success: function (data) {
                if ('full_name' in data) {
                    settings_change_success(i18n.t("Updated settings!"));
                } else {
                    settings_change_success(i18n.t("No changes made."));
                }
                overlays.close_modal('change_full_name_modal');
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Failed"), xhr, change_full_name_info);
            },
        });
    });

    $('#change_email_button').on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var change_email_info = $('#change_email_modal').find(".change_email_info").expectOne();

        var data = {};
        data.email = $('.email_change_container').find("input[name='email']").val();

        channel.patch({
            url: '/json/settings',
            data: data,
            success: function (data) {
                if ('account_email' in data) {
                    settings_change_success(data.account_email);
                    if (page_params.development_environment) {
                        var email_msg = templates.render('dev_env_email_access');
                        $("#account-settings-status").append(email_msg);
                    }
                } else {
                    settings_change_success(i18n.t("No changes made."));
                }
                overlays.close_modal('change_email_modal');
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Failed"), xhr, change_email_info);
            },
        });
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

    $('#settings_page').on('click', '.custom_user_field .remove_date', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var field = $(e.target).closest('.custom_user_field').expectOne();
        var field_id = parseInt($(field).attr("data-field-id"), 10);
        field.find(".custom_user_field_value").val("");
        update_user_custom_profile_fields([field_id], channel.del);
    });

    $('#settings_page').on('change', '.custom_user_field_value', function (e) {
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
        loading.make_indicator(spinner, {text: 'Uploading avatar.'});

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
