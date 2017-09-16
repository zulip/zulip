var settings_account = (function () {

var exports = {};

exports.update_email = function (new_email) {
    var email_input = $('#email_value');

    if (email_input) {
        email_input.text(new_email);
    }
};

function settings_change_error(message, xhr) {
    ui_report.error(message, xhr, $('#account-settings-status').expectOne());
}

function settings_change_success(message) {
    ui_report.success(message, $('#account-settings-status').expectOne());
}


exports.set_up = function () {
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
        $('#old_password, #new_password, #confirm_password').val('');
    }

    clear_password_change();

    $('#pw_change_link').on('click', function (e) {
        e.preventDefault();
        $('#pw_change_link').hide();
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

    $('#new_password').on('change keyup', function () {
        var field = $('#new_password');
        common.password_quality(field.val(), $('#pw_strength .bar'), field);
    });

    $("form.your-account-settings").ajaxForm({
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
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
        },
    });

    $('#change_email_button').on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        overlays.close_modal('change_email_modal');

        var data = {};
        data.email = $('.email_change_container').find("input[name='email']").val();

        channel.patch({
            url: '/json/settings',
            data: data,
            success: function (data) {
                if ('account_email' in data) {
                    settings_change_success(data.account_email);
                } else {
                    settings_change_success(i18n.t("No changes made."));
                }
            },
            error: function (xhr) {
                settings_change_error("Error changing settings", xhr);
            },
        });
    });

    $('#change_email').on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        overlays.open_modal('change_email_modal');
        var email = $('#email_value').text().trim();
        $('.email_change_container').find("input[name='email']").val(email);
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
                ui_report.error(i18n.t("Error deactivating account"), xhr, $('#account-settings-status').expectOne());
            },
        });
    });


    function upload_avatar(file_input) {
        var form_data = new FormData();

        form_data.append('csrfmiddlewaretoken', csrf_token);
        jQuery.each(file_input[0].files, function (i, file) {
            form_data.append('file-'+i, file);
        });

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
                $("#user-settings-avatar").expectOne().attr("src", data.avatar_url);
                $("#user_avatar_delete_button").show();
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
