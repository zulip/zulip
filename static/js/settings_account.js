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

function add_custom_profile_fields_to_settings() {
    var all_custom_fields = page_params.custom_profile_fields;

    all_custom_fields.forEach(function (field) {
        var type;
        var value = people.my_custom_profile_data(field.id);
        var is_long_text = field.type === 2;

        // 1 & 2 type represent textual data.
        if (field.type === 1 || field.type === 2) {
            type = "text";
        } else {
            blueslip.error("Undefined field type.");
        }
        if (value === undefined) {
            // If user has not set value for field.
            value = "";
        }

        var html = templates.render("custom-user-profile-field", {field_name: field.name,
                                                                  field_id: field.id,
                                                                  field_type: type,
                                                                  field_value: value,
                                                                  is_long_text_field: is_long_text,
                                                                  });
        $("#account-settings .custom-profile-fields-form").append(html);
    });
}

exports.set_up = function () {
    // Add custom profile fields elements to user account settings.
    add_custom_profile_fields_to_settings();
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
    $("#get_api_key_box form").ajaxForm({
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        success: function (resp, statusText, xhr) {
            var result = JSON.parse(xhr.responseText);
            var settings_status = $('#account-settings-status').expectOne();

            $("#get_api_key_password").val("");
            $("#api_key_value").text(result.api_key);
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
        $(this).attr("href", settings_bots.generate_zuliprc_uri(
            people.my_current_email(),
            $("#api_key_value").text()
        ));
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
            beforeSubmit: function () {
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
        e.preventDefault();
        e.stopPropagation();
        $("#deactivate_self_modal").modal("show");
    });

    $(".custom_user_field input, .custom_user_field textarea").on('change', function () {
        var fields = [];
        var value = $(this).val();
        var spinner = $("#custom-field-status").expectOne();
        loading.make_indicator(spinner, {text: 'Saving ...'});
        fields.push({id: parseInt($(this).attr("id"), 10), value: value});
        settings_ui.do_settings_change(channel.patch, "/json/users/me/profile_data",
                                       {data: JSON.stringify(fields)}, spinner);
    });

    $("#do_deactivate_self_button").on('click',function () {
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
                    window.location.href = "/login";
                },
                error: function (xhr) {
                    $("#deactivate_self_modal").modal("hide");
                    ui_report.error(i18n.t("Error deactivating account"), xhr, $('#account-settings-status').expectOne());
                },
            });
        }, 5000);
    });


    function upload_avatar(file_input) {
        var form_data = new FormData();

        form_data.append('csrfmiddlewaretoken', csrf_token);
        jQuery.each(file_input[0].files, function (i, file) {
            form_data.append('file-'+i, file);
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
            success: function (data) {
                loading.destroy_indicator($("#upload_avatar_spinner"));
                $("#user-avatar-block").expectOne().attr("src", data.avatar_url);
                $("#user_avatar_delete_button").show();
                $("#user-avatar-source").hide();
            },
            error: function () {
                if (page_params.avatar_source === 'G') {
                    $("#user-avatar-source").show();
                }
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
