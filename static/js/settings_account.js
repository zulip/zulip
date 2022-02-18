import $ from "jquery";

import render_change_email_modal from "../templates/change_email_modal.hbs";
import render_confirm_deactivate_own_user from "../templates/confirm_dialog/confirm_deactivate_own_user.hbs";
import render_dialog_change_password from "../templates/dialog_change_password.hbs";
import render_settings_api_key_modal from "../templates/settings/api_key_modal.hbs";
import render_settings_custom_user_profile_field from "../templates/settings/custom_user_profile_field.hbs";
import render_settings_dev_env_email_access from "../templates/settings/dev_env_email_access.hbs";

import * as avatar from "./avatar";
import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as common from "./common";
import * as confirm_dialog from "./confirm_dialog";
import {csrf_token} from "./csrf";
import * as dialog_widget from "./dialog_widget";
import {$t_html} from "./i18n";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as people from "./people";
import * as pill_typeahead from "./pill_typeahead";
import * as settings_bots from "./settings_bots";
import * as settings_data from "./settings_data";
import * as settings_ui from "./settings_ui";
import * as ui_report from "./ui_report";
import * as user_pill from "./user_pill";
import * as user_profile from "./user_profile";
import {user_settings} from "./user_settings";

let password_quality; // Loaded asynchronously

export function update_email(new_email) {
    const email_input = $("#change_email");

    if (email_input) {
        email_input.text(new_email);
    }
}

export function update_full_name(new_full_name) {
    // Arguably, this should work more like how the `update_email`
    // flow works, where we update the name in the modal on open,
    // rather than updating it here, but this works.
    const full_name_input = $(".full-name-change-form input[name='full_name']");
    if (full_name_input) {
        full_name_input.val(new_full_name);
    }
}

export function update_name_change_display() {
    if (!settings_data.user_can_change_name()) {
        $("#full_name").prop("disabled", true);
        $(".change_name_tooltip").show();
    } else {
        $("#full_name").prop("disabled", false);
        $(".change_name_tooltip").hide();
    }
}

export function update_email_change_display() {
    if (page_params.realm_email_changes_disabled && !page_params.is_admin) {
        $("#change_email").prop("disabled", true);
        $(".change_email_tooltip").show();
    } else {
        $("#change_email").prop("disabled", false);
        $(".change_email_tooltip").hide();
    }
}

export function update_avatar_change_display() {
    if (!settings_data.user_can_change_avatar()) {
        // We disable this widget by simply hiding its edit UI.
        $("#user-avatar-upload-widget .image_upload_button").hide();
        $(".user-avatar-section .settings-info-icon").show();
    } else {
        $("#user-avatar-upload-widget .image_upload_button").show();
        $(".user-avatar-section .settings-info-icon").hide();
    }
}

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

function settings_change_error(message_html, xhr) {
    ui_report.error(message_html, xhr, $("#account-settings-status").expectOne());
}

function update_custom_profile_field(field, method) {
    let field_id;
    if (method === channel.del) {
        field_id = field;
    } else {
        field_id = field.id;
    }

    const spinner_element = $(
        `.custom_user_field[data-field-id="${CSS.escape(field_id)}"] .custom-field-status`,
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

export function append_custom_profile_fields(element_id, user_id) {
    const person = people.get_by_user_id(user_id);
    if (person.is_bot) {
        return;
    }
    const all_custom_fields = page_params.custom_profile_fields;
    const all_field_types = page_params.custom_profile_field_types;

    const all_field_template_types = new Map([
        [all_field_types.LONG_TEXT.id, "text"],
        [all_field_types.SHORT_TEXT.id, "text"],
        [all_field_types.SELECT.id, "select"],
        [all_field_types.USER.id, "user"],
        [all_field_types.DATE.id, "date"],
        [all_field_types.EXTERNAL_ACCOUNT.id, "text"],
        [all_field_types.URL.id, "url"],
    ]);

    for (const field of all_custom_fields) {
        let field_value = people.get_custom_profile_data(user_id, field.id);
        const is_select_field = field.type === all_field_types.SELECT.id;
        const field_choices = [];

        if (field_value === undefined || field_value === null) {
            field_value = {value: "", rendered_value: ""};
        }
        if (is_select_field) {
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
            is_select_field,
            field_choices,
        });
        $(element_id).append(html);
    }
}

export function initialize_custom_date_type_fields(element_id) {
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
}

export function initialize_custom_user_type_fields(
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

    for (const field of page_params.custom_profile_fields) {
        let field_value_raw = people.get_custom_profile_data(user_id, field.id);

        if (field_value_raw) {
            field_value_raw = field_value_raw.value;
        }

        // If field is not editable and field value is null, we don't expect
        // pill container for that field and proceed further
        if (field.type === field_types.USER.id && (field_value_raw || is_editable)) {
            const pill_container = $(element_id)
                .find(`.custom_user_field[data-field-id="${CSS.escape(field.id)}"] .pill-container`)
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
                    for (const pill_user_id of field_value) {
                        const user = people.get_by_user_id(pill_user_id);
                        user_pill.append_user(user, pills);
                    }
                }
            }

            if (is_editable) {
                const input = pill_container.children(".input");
                if (set_handler_on_update) {
                    const opts = {update_func: update_custom_user_field, user: true};
                    pill_typeahead.set_up(input, pills, opts);
                    pills.onPillRemove(() => {
                        update_custom_user_field();
                    });
                } else {
                    pill_typeahead.set_up(input, pills, {user: true});
                }
            }
            user_pills.set(field.id, pills);
        }
    }

    return user_pills;
}

export function add_custom_profile_fields_to_settings() {
    if (!overlays.settings_open()) {
        return;
    }

    const element_id = "#profile-settings .custom-profile-fields-form";
    $(element_id).html("");

    append_custom_profile_fields(element_id, people.my_current_user_id());
    initialize_custom_user_type_fields(element_id, people.my_current_user_id(), true, true);
    initialize_custom_date_type_fields(element_id);
}

export function hide_confirm_email_banner() {
    if (!overlays.settings_open()) {
        return;
    }
    $("#account-settings-status").hide();
}

export function set_up() {
    // Add custom profile fields elements to user account settings.
    add_custom_profile_fields_to_settings();
    $("#account-settings-status").hide();

    const setup_api_key_modal = () => {
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
                    $("#get_api_key_button").hide();
                    $("#show_api_key").show();
                    $("#api_key_buttons").show();
                },
                error(xhr) {
                    ui_report.error(
                        $t_html({defaultMessage: "Error"}),
                        xhr,
                        $("#api_key_status").expectOne(),
                    );
                    $("#show_api_key").hide();
                },
            });
        }

        $("#api_key_value").text("");
        $("#show_api_key").hide();
        $("#api_key_buttons").hide();
        common.setup_password_visibility_toggle(
            "#get_api_key_password",
            "#get_api_key_password + .password_visibility_toggle",
            {tippy_tooltips: true},
        );

        function do_get_api_key() {
            $("#api_key_status").hide();
            const data = {};
            data.password = $("#get_api_key_password").val();
            request_api_key(data);
        }

        if (page_params.realm_password_auth_enabled === false) {
            // Skip the password prompt step, since the user doesn't have one.
            request_api_key({});
        } else {
            $("#get_api_key_button").on("click", (e) => {
                e.preventDefault();
                e.stopPropagation();
                do_get_api_key();
            });
            $("#get_api_key_password").on("keydown", (e) => {
                if (e.key === "Enter") {
                    e.preventDefault();
                    e.stopPropagation();
                    do_get_api_key();
                }
            });
        }

        $("#regenerate_api_key").on("click", (e) => {
            const email = page_params.delivery_email;
            const api_key = $("#api_key_value").text();
            const authorization_header = "Basic " + btoa(`${email}:${api_key}`);

            channel.post({
                // This endpoint is only accessible with the previous API key,
                // via our usual HTTP Basic auth mechanism.
                url: "/api/v1/users/me/api_key/regenerate",
                headers: {Authorization: authorization_header},
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

        $("#api_key_modal [data-micromodal-close]").on("click", () => {
            common.reset_password_toggle_icons(
                "#get_api_key_password",
                "#get_api_key_password + .password_visibility_toggle",
            );
        });
    };

    $("#api_key_button").on("click", (e) => {
        $("body").append(render_settings_api_key_modal());
        setup_api_key_modal();
        $("#api_key_status").hide();
        overlays.open_modal("api_key_modal", {
            autoremove: true,
            micromodal: true,
            on_show: () => {
                $("#get_api_key_password").trigger("focus");
            },
        });
        e.preventDefault();
        e.stopPropagation();
    });

    function clear_password_change() {
        // Clear the password boxes so that passwords don't linger in the DOM
        // for an XSS attacker to find.
        common.reset_password_toggle_icons(
            "#old_password",
            "#old_password + .password_visibility_toggle",
        );
        common.reset_password_toggle_icons(
            "#new_password",
            "#new_password + .password_visibility_toggle",
        );
        $("#old_password, #new_password").val("");
        password_quality?.("", $("#pw_strength .bar"), $("#new_password"));
    }

    function change_password_post_render() {
        $("#change_password_modal")
            .find("[data-micromodal-close]")
            .on("click", () => {
                clear_password_change();
            });
        common.setup_password_visibility_toggle(
            "#old_password",
            "#old_password + .password_visibility_toggle",
            {tippy_tooltips: true},
        );
        common.setup_password_visibility_toggle(
            "#new_password",
            "#new_password + .password_visibility_toggle",
            {tippy_tooltips: true},
        );
        clear_password_change();
    }

    $("#change_password").on("click", async (e) => {
        e.preventDefault();
        e.stopPropagation();

        function validate_input(e) {
            e.preventDefault();
            e.stopPropagation();
            const old_password = $("#old_password").val();
            const new_password = $("#new_password").val();

            if (old_password === "") {
                ui_report.error(
                    $t_html({defaultMessage: "Please enter your password"}),
                    undefined,
                    $("#dialog_error"),
                );
                return false;
            }

            if (new_password === "") {
                ui_report.error(
                    $t_html({defaultMessage: "Please choose a new password"}),
                    undefined,
                    $("#dialog_error"),
                );
                return false;
            }
            return true;
        }

        dialog_widget.launch({
            html_heading: $t_html({defaultMessage: "Change password"}),
            html_body: render_dialog_change_password(),
            html_submit_button: $t_html({defaultMessage: "Change"}),
            loading_spinner: true,
            id: "change_password_modal",
            form_id: "change_password_container",
            post_render: change_password_post_render,
            on_click: do_change_password,
            validate_input,
        });
        $("#pw_change_controls").show();
        if (page_params.realm_password_auth_enabled !== false) {
            // zxcvbn.js is pretty big, and is only needed on password
            // change, so load it asynchronously.
            password_quality = (await import("./password_quality")).password_quality;
            $("#pw_strength .bar").removeClass("fade");
        }
    });

    function do_change_password(e) {
        e.preventDefault();
        e.stopPropagation();
        const change_password_error = $("#change_password_modal").find("#dialog_error");
        change_password_error.hide();

        const data = {
            old_password: $("#old_password").val(),
            new_password: $("#new_password").val(),
        };

        const new_pw_field = $("#new_password");
        const new_pw = data.new_password;
        if (new_pw !== "") {
            if (password_quality === undefined) {
                // password_quality didn't load, for whatever reason.
                settings_change_error(
                    "An internal error occurred; try reloading the page. " +
                        "Sorry for the trouble!",
                );
                return;
            } else if (!password_quality(new_pw, undefined, new_pw_field)) {
                settings_change_error($t_html({defaultMessage: "New password is too weak"}));
                return;
            }
        }

        channel.set_password_change_in_progress(true);
        const opts = {
            success_continuation() {
                channel.set_password_change_in_progress(false);
                dialog_widget.close_modal();
            },
            error_continuation() {
                dialog_widget.hide_dialog_spinner();
                channel.set_password_change_in_progress(false);
            },
            error_msg_element: change_password_error,
            failure_msg_html: null,
        };
        settings_ui.do_settings_change(
            channel.patch,
            "/json/settings",
            data,
            $("#account-settings-status").expectOne(),
            opts,
        );
        clear_password_change();
    }

    $("#new_password").on("input", () => {
        const field = $("#new_password");
        password_quality?.(field.val(), $("#pw_strength .bar"), field);
    });

    $("#full_name").on("change", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const data = {};

        data.full_name = $("#full_name").val();

        settings_ui.do_settings_change(
            channel.patch,
            "/json/settings",
            data,
            $(".full-name-status").expectOne(),
        );
    });

    function do_change_email(e) {
        e.preventDefault();
        e.stopPropagation();
        const change_email_error = $("#change_email_modal").find("#dialog_error");
        const data = {};
        data.email = $("#change_email_container").find("input[name='email']").val();

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
                dialog_widget.close_modal();
            },
            error_continuation() {
                dialog_widget.hide_dialog_spinner();
            },
            error_msg_element: change_email_error,
            success_msg_html: $t_html(
                {defaultMessage: "Check your email ({email}) to confirm the new address."},
                {email: data.email},
            ),
            sticky: true,
        };
        settings_ui.do_settings_change(
            channel.patch,
            "/json/settings",
            data,
            $("#account-settings-status").expectOne(),
            opts,
        );
    }

    function change_email_post_render() {
        const input_elem = $("#change_email_container").find("input[name='email']");
        const email = $("#change_email").text().trim();
        input_elem.val(email);
    }

    $("#change_email").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!page_params.realm_email_changes_disabled || page_params.is_admin) {
            dialog_widget.launch({
                html_heading: $t_html({defaultMessage: "Change email"}),
                html_body: render_change_email_modal(),
                html_submit_button: $t_html({defaultMessage: "Change"}),
                loading_spinner: true,
                id: "change_email_modal",
                form_id: "change_email_container",
                on_click: do_change_email,
                post_render: change_email_post_render,
                on_shown: () => {
                    $("#change_email_container input").trigger("focus");
                },
            });
        }
    });

    $("#profile-settings").on("click", ".custom_user_field .remove_date", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const field = $(e.target).closest(".custom_user_field").expectOne();
        const field_id = Number.parseInt($(field).attr("data-field-id"), 10);
        update_user_custom_profile_fields([field_id], channel.del);
    });

    $("#profile-settings").on("change", ".custom_user_field_value", function (e) {
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

    $("#user_deactivate_account_button").on("click", (e) => {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active_modal` in `settings.js`.
        e.preventDefault();
        e.stopPropagation();

        function handle_confirm() {
            channel.del({
                url: "/json/users/me",
                success() {
                    dialog_widget.hide_dialog_spinner();
                    dialog_widget.close_modal();
                    window.location.href = "/login/";
                },
                error(xhr) {
                    const error_last_owner = $t_html({
                        defaultMessage: "Error: Cannot deactivate the only organization owner.",
                    });
                    const error_last_user = $t_html(
                        {
                            defaultMessage:
                                "Error: Cannot deactivate the only user. You can deactivate the whole organization though in your <z-link>organization profile settings</z-link>.",
                        },
                        {
                            "z-link": (content_html) =>
                                `<a target="_blank" href="/#organization/organization-profile">${content_html}</a>`,
                        },
                    );
                    let rendered_error_msg;
                    if (xhr.responseJSON.code === "CANNOT_DEACTIVATE_LAST_USER") {
                        if (xhr.responseJSON.is_last_owner) {
                            rendered_error_msg = error_last_owner;
                        } else {
                            rendered_error_msg = error_last_user;
                        }
                    }
                    dialog_widget.hide_dialog_spinner();
                    dialog_widget.close_modal();
                    $("#account-settings-status")
                        .addClass("alert-error")
                        .html(rendered_error_msg)
                        .show();
                },
            });
        }
        const html_body = render_confirm_deactivate_own_user();
        confirm_dialog.launch({
            html_heading: $t_html({defaultMessage: "Deactivate your account"}),
            html_body,
            on_click: handle_confirm,
            help_link: "/help/deactivate-your-account",
            loading_spinner: true,
        });
    });

    $("#show_my_user_profile_modal").on("click", () => {
        overlays.close_overlay("settings");
        const user = people.get_by_user_id(people.my_current_user_id());
        setTimeout(() => {
            user_profile.show_user_profile(user);
        }, 100);

        // If user opened the "preview profile" modal from user
        // settings, then closing preview profile modal should
        // send them back to the settings modal.
        $("body").one("hidden.bs.modal", "#user-profile-modal", (e) => {
            e.preventDefault();
            e.stopPropagation();

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

    $("#user_timezone").val(user_settings.timezone);

    $("#user_timezone").on("change", function (e) {
        e.preventDefault();
        e.stopPropagation();

        const data = {timezone: this.value};

        settings_ui.do_settings_change(
            channel.patch,
            "/json/settings",
            data,
            $(".timezone-setting-status").expectOne(),
        );
    });

    $("#privacy_settings_box").on("change", "input", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const input_elem = $(e.currentTarget);
        const setting_name = input_elem.attr("name");
        const checked = input_elem.prop("checked");

        const data = {[setting_name]: checked};
        settings_ui.do_settings_change(
            channel.patch,
            "/json/settings",
            data,
            $("#account-settings .privacy-setting-status").expectOne(),
        );
    });
}
