"use strict";

const _ = require("lodash");

const render_settings_api_key_modal = require("../templates/settings/api_key_modal.hbs");
const render_settings_custom_user_profile_field = require("../templates/settings/custom_user_profile_field.hbs");
const render_settings_dev_env_email_access = require("../templates/settings/dev_env_email_access.hbs");

const people = require("./people");
const setup = require("./setup");

exports.update_email = function (new_email) {
    const email_input = $("#email_value");

    if (email_input) {
        email_input.text(new_email);
    }
};

exports.update_full_name = function (new_full_name) {
    const full_name_field = $("#full_name_value");
    if (full_name_field) {
        full_name_field.text(new_full_name);
    }

    // Arguably, this should work more like how the `update_email`
    // flow works, where we update the name in the modal on open,
    // rather than updating it here, but this works.
    const full_name_input = $(".full_name_change_container input[name='full_name']");
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

exports.user_can_change_avatar = function () {
    if (page_params.is_admin) {
        return true;
    }
    if (page_params.realm_avatar_changes_disabled || page_params.server_avatar_changes_disabled) {
        return false;
    }
    return true;
};

exports.update_name_change_display = function () {
    if (!exports.user_can_change_name()) {
        $("#full_name").prop("disabled", true);
        $(".change_name_tooltip").show();
    } else {
        $("#full_name").prop("disabled", false);
        $(".change_name_tooltip").hide();
    }
};

exports.update_email_change_display = function () {
    if (page_params.realm_email_changes_disabled && !page_params.is_admin) {
        $("#change_email .button").prop("disabled", true);
        $(".change_email_tooltip").show();
    } else {
        $("#change_email .button").prop("disabled", false);
        $(".change_email_tooltip").hide();
    }
};

exports.update_avatar_change_display = function () {
    if (!exports.user_can_change_avatar()) {
        $("#user-avatar-upload-widget .image_upload_button").prop("disabled", true);
        $("#user-avatar-upload-widget .image-delete-button .button").prop("disabled", true);
    } else {
        $("#user-avatar-upload-widget .image_upload_button").prop("disabled", false);
        $("#user-avatar-upload-widget .image-delete-button .button").prop("disabled", false);
    }
};

function display_avatar_upload_complete() {
    $("#user-avatar-upload-widget .upload-spinner-background").css({visibility: "hidden"});
    $("#user-avatar-upload-widget .image-upload-text").show();
    $("#user-avatar-upload-widget .image-delete-button").show();
}

function display_avatar_upload_started() {
    $("#user-avatar-source").hide();
    $("#user-avatar-upload-widget .upload-spinner-background").css({visibility: "visible"});
    $("#user-avatar-upload-widget .image-upload-text").hide();
    $("#user-avatar-upload-widget .image-delete-button").hide();
}

function settings_change_error(message, xhr) {
    ui_report.error(message, xhr, $("#account-settings-status").expectOne());
}

function update_custom_profile_field(field, method) {
    let field_id;
    if (method === channel.del) {
        field_id = field;
    } else {
        field_id = field.id;
    }

    const spinner_element = $(
        '.custom_user_field[data-field-id="' + field_id + '"] .custom-field-status',
    ).expectOne();
    settings_ui.do_settings_change(
        method,
        "/json/users/me/profile_data",
        {data: JSON.stringify([field])},
        spinner_element,
    );
}

function update_user_custom_profile_fields(fields, method) {
    if (method === undefined) {
        blueslip.error("Undefined method in update_user_custom_profile_fields");
    }

    for (const field of fields) {
        update_custom_profile_field(field, method);
    }
}

exports.append_custom_profile_fields = function (element_id, user_id) {
    const person = people.get_by_user_id(user_id);
    if (person.is_bot) {
        return;
    }
    const all_custom_fields = page_params.custom_profile_fields;
    const all_field_types = page_params.custom_profile_field_types;

    const all_field_template_types = new Map([
        [all_field_types.LONG_TEXT.id, "text"],
        [all_field_types.SHORT_TEXT.id, "text"],
        [all_field_types.CHOICE.id, "choice"],
        [all_field_types.USER.id, "user"],
        [all_field_types.DATE.id, "date"],
        [all_field_types.EXTERNAL_ACCOUNT.id, "text"],
        [all_field_types.URL.id, "url"],
    ]);

    all_custom_fields.forEach((field) => {
        let field_value = people.get_custom_profile_data(user_id, field.id);
        const is_choice_field = field.type === all_field_types.CHOICE.id;
        const field_choices = [];

        if (field_value === undefined || field_value === null) {
            field_value = {value: "", rendered_value: ""};
        }
        if (is_choice_field) {
            const field_choice_dict = JSON.parse(field.field_data);
            for (const choice in field_choice_dict) {
                if (choice) {
                    field_choices[field_choice_dict[choice].order] = {
                        value: choice,
                        text: field_choice_dict[choice].text,
                        selected: choice === field_value.value,
                    };
                }
            }
        }

        const html = render_settings_custom_user_profile_field({
            field,
            field_type: all_field_template_types.get(field.type),
            field_value,
            is_long_text_field: field.type === all_field_types.LONG_TEXT.id,
            is_user_field: field.type === all_field_types.USER.id,
            is_date_field: field.type === all_field_types.DATE.id,
            is_choice_field,
            field_choices,
        });
        $(element_id).append(html);
    });
};

exports.initialize_custom_date_type_fields = function (element_id) {
    $(element_id).find(".custom_user_field .datepicker").flatpickr({
        altInput: true,
        altFormat: "F j, Y",
        allowInput: true,
    });

    $(element_id)
        .find(".custom_user_field .datepicker")
        .on("mouseenter", function () {
            if ($(this).val().length <= 0) {
                $(this).parent().find(".remove_date").hide();
            } else {
                $(this).parent().find(".remove_date").show();
            }
        });

    $(element_id)
        .find(".custom_user_field .remove_date")
        .on("click", function () {
            $(this).parent().find(".custom_user_field_value").val("");
        });
};

exports.initialize_custom_user_type_fields = function (
    element_id,
    user_id,
    is_editable,
    set_handler_on_update,
) {
    const field_types = page_params.custom_profile_field_types;
    const user_pills = new Map();

    const person = people.get_by_user_id(user_id);
    if (person.is_bot) {
        return user_pills;
    }

    page_params.custom_profile_fields.forEach((field) => {
        let field_value_raw = people.get_custom_profile_data(user_id, field.id);

        if (field_value_raw) {
            field_value_raw = field_value_raw.value;
        }

        // If field is not editable and field value is null, we don't expect
        // pill container for that field and proceed further
        if (field.type === field_types.USER.id && (field_value_raw || is_editable)) {
            const pill_container = $(element_id)
                .find('.custom_user_field[data-field-id="' + field.id + '"] .pill-container')
                .expectOne();
            const pills = user_pill.create_pills(pill_container);

            function update_custom_user_field() {
                const fields = [];
                const user_ids = user_pill.get_user_ids(pills);
                if (user_ids.length < 1) {
                    fields.push(field.id);
                    update_user_custom_profile_fields(fields, channel.del);
                } else {
                    fields.push({id: field.id, value: user_ids});
                    update_user_custom_profile_fields(fields, channel.patch);
                }
            }

            if (field_value_raw) {
                const field_value = JSON.parse(field_value_raw);
                if (field_value) {
                    field_value.forEach((pill_user_id) => {
                        const user = people.get_by_user_id(pill_user_id);
                        user_pill.append_user(user, pills);
                    });
                }
            }

            if (is_editable) {
                const input = pill_container.children(".input");
                if (set_handler_on_update) {
                    const opts = {update_func: update_custom_user_field};
                    pill_typeahead.set_up(input, pills, opts);
                    pills.onPillRemove(() => {
                        update_custom_user_field();
                    });
                } else {
                    pill_typeahead.set_up(input, pills, {});
                }
            }
            user_pills.set(field.id, pills);
        }
    });

    return user_pills;
};

exports.add_custom_profile_fields_to_settings = function () {
    if (!overlays.settings_open()) {
        return;
    }

    const element_id = "#account-settings .custom-profile-fields-form";
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

    const setup_api_key_modal = _.once(() => {
        function request_api_key(data) {
            channel.post({
                url: "/json/fetch_api_key",
                data,
                success(data) {
                    $("#get_api_key_password").val("");
                    $("#api_key_value").text(data.api_key);
                    // The display property on the error bar is set to important
                    // so instead of making display: none !important we just
                    // remove it.
                    $("#api_key_status").remove();
                    $("#password_confirmation").hide();
                    $("#show_api_key").show();
                },
                error(xhr) {
                    ui_report.error(i18n.t("Error"), xhr, $("#api_key_status").expectOne());
                    $("#show_api_key").hide();
                    $("#api_key_modal").show();
                },
            });
        }

        $(".account-settings-form").append(render_settings_api_key_modal());
        $("#api_key_value").text("");
        $("#show_api_key").hide();

        if (page_params.realm_password_auth_enabled === false) {
            // Skip the password prompt step, since the user doesn't have one.
            request_api_key({});
        } else {
            $("#get_api_key_button").on("click", (e) => {
                const data = {};
                e.preventDefault();
                e.stopPropagation();

                data.password = $("#get_api_key_password").val();
                request_api_key(data);
            });
        }

        $("#show_api_key").on("click", "button.regenerate_api_key", (e) => {
            channel.post({
                url: "/json/users/me/api_key/regenerate",
                success(data) {
                    $("#api_key_value").text(data.api_key);
                },
                error(xhr) {
                    $("#user_api_key_error").text(JSON.parse(xhr.responseText).msg).show();
                },
            });
            e.preventDefault();
            e.stopPropagation();
        });

        $("#download_zuliprc").on("click", function () {
            const bot_object = {
                user_id: people.my_current_user_id(),
                email: page_params.delivery_email,
                api_key: $("#api_key_value").text(),
            };
            const data = settings_bots.generate_zuliprc_content(bot_object);
            $(this).attr("href", settings_bots.encode_zuliprc_as_uri(data));
        });
    });

    $("#api_key_button").on("click", (e) => {
        setup_api_key_modal();
        overlays.open_modal("#api_key_modal");
        e.preventDefault();
        e.stopPropagation();
    });

    function clear_password_change() {
        // Clear the password boxes so that passwords don't linger in the DOM
        // for an XSS attacker to find.
        $("#old_password, #new_password").val("");
        common.password_quality("", $("#pw_strength .bar"), $("#new_password"));
    }

    clear_password_change();

    $("#change_full_name").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (exports.user_can_change_name()) {
            $("#change_full_name_modal").find("input[name='full_name']").val(page_params.full_name);
            overlays.open_modal("#change_full_name_modal");
        }
    });

    $("#change_password").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        overlays.open_modal("#change_password_modal");
        $("#pw_change_controls").show();
        if (page_params.realm_password_auth_enabled !== false) {
            // zxcvbn.js is pretty big, and is only needed on password
            // change, so load it asynchronously.
            require(["zxcvbn"], (zxcvbn) => {
                window.zxcvbn = zxcvbn;
                $("#pw_strength .bar").removeClass("fade");
            });
        }
    });

    $("#change_password_modal")
        .find("[data-dismiss=modal]")
        .on("click", () => {
            clear_password_change();
        });

    // If the modal is closed using the 'close' button or the 'Cancel' button
    $(".modal")
        .find("[data-dismiss=modal]")
        .on("click", () => {
            // Enable mouse events for the background on closing modal
            $(".overlay.show").attr("style", null);
        });

    $("#change_password_button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const change_password_error = $("#change_password_modal")
            .find(".change_password_info")
            .expectOne();

        const data = {
            old_password: $("#old_password").val(),
            new_password: $("#new_password").val(),
            confirm_password: $("#confirm_password").val(),
        };

        const new_pw_field = $("#new_password");
        const new_pw = data.new_password;
        if (new_pw !== "") {
            const password_ok = common.password_quality(new_pw, undefined, new_pw_field);
            if (password_ok === undefined) {
                // zxcvbn.js didn't load, for whatever reason.
                settings_change_error(
                    "An internal error occurred; try reloading the page. " +
                        "Sorry for the trouble!",
                );
                return;
            } else if (!password_ok) {
                settings_change_error(i18n.t("New password is too weak"));
                return;
            }
        }

        setup.set_password_change_in_progress(true);
        const opts = {
            success_continuation() {
                setup.set_password_change_in_progress(false);
                overlays.close_modal("#change_password_modal");
            },
            error_continuation() {
                setup.set_password_change_in_progress(false);
            },
            error_msg_element: change_password_error,
        };
        settings_ui.do_settings_change(
            channel.patch,
            "/json/settings",
            data,
            $("#account-settings-status").expectOne(),
            opts,
        );
        clear_password_change();
    });

    $("#new_password").on("input", () => {
        const field = $("#new_password");
        common.password_quality(field.val(), $("#pw_strength .bar"), field);
    });

    $("#change_full_name_button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const change_full_name_error = $("#change_full_name_modal")
            .find(".change_full_name_info")
            .expectOne();
        const data = {};

        data.full_name = $(".full_name_change_container").find("input[name='full_name']").val();

        const opts = {
            success_continuation() {
                overlays.close_modal("#change_full_name_modal");
            },
            error_msg_element: change_full_name_error,
        };
        settings_ui.do_settings_change(
            channel.patch,
            "/json/settings",
            data,
            $("#account-settings-status").expectOne(),
            opts,
        );
    });

    $("#change_email_button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const change_email_error = $("#change_email_modal").find(".change_email_info").expectOne();
        const data = {};
        data.email = $(".email_change_container").find("input[name='email']").val();

        const opts = {
            success_continuation() {
                if (page_params.development_environment) {
                    const email_msg = render_settings_dev_env_email_access();
                    ui_report.success(
                        email_msg,
                        $("#dev-account-settings-status").expectOne(),
                        4000,
                    );
                }
                overlays.close_modal("#change_email_modal");
            },
            error_msg_element: change_email_error,
            success_msg: i18n
                .t("Check your email (%s) to confirm the new address.")
                .replace("%s", data.email),
        };
        settings_ui.do_settings_change(
            channel.patch,
            "/json/settings",
            data,
            $("#account-settings-status").expectOne(),
            opts,
        );
    });

    $("#change_email").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!page_params.realm_email_changes_disabled || page_params.is_admin) {
            overlays.open_modal("#change_email_modal");
            const email = $("#email_value").text().trim();
            $(".email_change_container").find("input[name='email']").val(email);
        }
    });

    $("#user_deactivate_account_button").on("click", (e) => {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active_modal` in `settings.js`.
        e.preventDefault();
        e.stopPropagation();
        $("#deactivate_self_modal").modal("show");
    });

    $("#account-settings").on("click", ".custom_user_field .remove_date", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const field = $(e.target).closest(".custom_user_field").expectOne();
        const field_id = Number.parseInt($(field).attr("data-field-id"), 10);
        update_user_custom_profile_fields([field_id], channel.del);
    });

    $("#account-settings").on("change", ".custom_user_field_value", function (e) {
        const fields = [];
        const value = $(this).val();
        const field_id = Number.parseInt(
            $(e.target).closest(".custom_user_field").attr("data-field-id"),
            10,
        );
        if (value) {
            fields.push({id: field_id, value});
            update_user_custom_profile_fields(fields, channel.patch);
        } else {
            fields.push(field_id);
            update_user_custom_profile_fields(fields, channel.del);
        }
    });

    $("#do_deactivate_self_button").on("click", () => {
        $("#do_deactivate_self_button .loader").css("display", "inline-block");
        $("#do_deactivate_self_button span").hide();
        $("#do_deactivate_self_button object").on("load", function () {
            const doc = this.getSVGDocument();
            const $svg = $(doc).find("svg");
            $svg.find("rect").css("fill", "#000");
        });

        setTimeout(() => {
            channel.del({
                url: "/json/users/me",
                success() {
                    $("#deactivate_self_modal").modal("hide");
                    window.location.href = "/login/";
                },
                error(xhr) {
                    const error_last_owner = i18n.t(
                        "Error: Cannot deactivate the only organization owner.",
                    );
                    const error_last_user = i18n.t(
                        'Error: Cannot deactivate the only user. You can deactivate the whole organization though in your <a target="_blank" href="/#organization/organization-profile">Organization profile settings</a>.',
                    );
                    let rendered_error_msg;
                    if (xhr.responseJSON.code === "CANNOT_DEACTIVATE_LAST_USER") {
                        if (xhr.responseJSON.is_last_owner) {
                            rendered_error_msg = error_last_owner;
                        } else {
                            rendered_error_msg = error_last_user;
                        }
                    }
                    $("#deactivate_self_modal").modal("hide");
                    $("#account-settings-status")
                        .addClass("alert-error")
                        .html(rendered_error_msg)
                        .show();
                },
            });
        }, 5000);
    });

    $("#show_my_user_profile_modal").on("click", () => {
        overlays.close_overlay("settings");
        const user = people.get_by_user_id(people.my_current_user_id());
        setTimeout(() => {
            popovers.show_user_profile(user);
        }, 100);

        // If user opened the "preview profile" modal from user
        // settings, then closing preview profile modal should
        // send them back to the settings modal.
        $("body").one("hidden.bs.modal", "#user-profile-modal", (e) => {
            e.preventDefault();
            e.stopPropagation();
            popovers.hide_user_profile();

            setTimeout(() => {
                if (!overlays.settings_open()) {
                    overlays.open_settings();
                }
            }, 100);
        });
    });

    function upload_avatar(file_input) {
        const form_data = new FormData();

        form_data.append("csrfmiddlewaretoken", csrf_token);
        for (const [i, file] of Array.prototype.entries.call(file_input[0].files)) {
            form_data.append("file-" + i, file);
        }
        display_avatar_upload_started();
        channel.post({
            url: "/json/users/me/avatar",
            data: form_data,
            cache: false,
            processData: false,
            contentType: false,
            success() {
                display_avatar_upload_complete();
                $("#user-avatar-upload-widget .image_file_input_error").hide();
                $("#user-avatar-source").hide();
                // Rest of the work is done via the user_events -> avatar_url event we will get
            },
            error(xhr) {
                display_avatar_upload_complete();
                if (page_params.avatar_source === "G") {
                    $("#user-avatar-source").show();
                }
                const $error = $("#user-avatar-upload-widget .image_file_input_error");
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

window.settings_account = exports;
