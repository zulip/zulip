import $ from "jquery";

import render_change_email_modal from "../templates/change_email_modal.hbs";
import render_confirm_deactivate_own_user from "../templates/confirm_dialog/confirm_deactivate_own_user.hbs";
import render_demo_organization_add_email_modal from "../templates/demo_organization_add_email_modal.hbs";
import render_dialog_change_password from "../templates/dialog_change_password.hbs";
import render_settings_api_key_modal from "../templates/settings/api_key_modal.hbs";
import render_settings_dev_env_email_access from "../templates/settings/dev_env_email_access.hbs";

import * as avatar from "./avatar";
import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as common from "./common";
import * as confirm_dialog from "./confirm_dialog";
import {csrf_token} from "./csrf";
import * as custom_profile_fields_ui from "./custom_profile_fields_ui";
import * as dialog_widget from "./dialog_widget";
import {$t_html} from "./i18n";
import * as keydown_util from "./keydown_util";
import * as modals from "./modals";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as people from "./people";
import * as settings_bots from "./settings_bots";
import * as settings_data from "./settings_data";
import * as settings_org from "./settings_org";
import * as settings_ui from "./settings_ui";
import {current_user, realm} from "./state_data";
import * as ui_report from "./ui_report";
import * as ui_util from "./ui_util";
import * as user_pill from "./user_pill";
import * as user_profile from "./user_profile";
import {user_settings} from "./user_settings";

let password_quality; // Loaded asynchronously
let user_avatar_widget_created = false;

export function update_email(new_email) {
    const $email_input = $("#change_email_button");

    if ($email_input) {
        $email_input.text(new_email);
    }
}

export function update_full_name(new_full_name) {
    // Arguably, this should work more like how the `update_email`
    // flow works, where we update the name in the modal on open,
    // rather than updating it here, but this works.
    const $full_name_input = $(".full-name-change-container input[name='full_name']");
    if ($full_name_input) {
        $full_name_input.val(new_full_name);
    }
}

export function update_name_change_display() {
    if ($("#user_details_section").length === 0) {
        return;
    }

    if (!settings_data.user_can_change_name()) {
        $("#full_name").prop("disabled", true);
        $("#full_name_input_container").addClass("disabled_setting_tooltip");
    } else {
        $("#full_name").prop("disabled", false);
        $("#full_name_input_container").removeClass("disabled_setting_tooltip");
    }
}

export function update_email_change_display() {
    if ($("#user_details_section").length === 0) {
        return;
    }

    if (!settings_data.user_can_change_email()) {
        $("#change_email_button").prop("disabled", true);
        $("#change_email_button_container").addClass("disabled_setting_tooltip");
    } else {
        $("#change_email_button").prop("disabled", false);
        $("#change_email_button_container").removeClass("disabled_setting_tooltip");
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

function upload_avatar($file_input) {
    const form_data = new FormData();

    form_data.append("csrfmiddlewaretoken", csrf_token);
    for (const [i, file] of Array.prototype.entries.call($file_input[0].files)) {
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
            if (current_user.avatar_source === "G") {
                $("#user-avatar-source").show();
            }
            if (xhr.responseJSON?.msg) {
                const $error = $("#user-avatar-upload-widget .image_file_input_error");
                $error.text(xhr.responseJSON.msg);
                $error.show();
            }
        },
    });
}

export function update_avatar_change_display() {
    if ($("#user-avatar-upload-widget").length === 0) {
        return;
    }

    if (!settings_data.user_can_change_avatar()) {
        $("#user-avatar-upload-widget .image_upload_button").addClass("hide");
        $("#user-avatar-upload-widget .image-disabled").removeClass("hide");
    } else {
        if (user_avatar_widget_created === false) {
            avatar.build_user_avatar_widget(upload_avatar);
            user_avatar_widget_created = true;
        }
        $("#user-avatar-upload-widget .image_upload_button").removeClass("hide");
        $("#user-avatar-upload-widget .image-disabled").addClass("hide");
    }
}

export function update_account_settings_display() {
    if ($("#user_details_section").length === 0) {
        return;
    }

    update_name_change_display();
    update_email_change_display();
    update_avatar_change_display();
}

export function maybe_update_deactivate_account_button() {
    if (!current_user.is_owner) {
        return;
    }

    const $deactivate_account_container = $("#deactivate_account_container");
    if ($deactivate_account_container) {
        if (people.is_current_user_only_owner()) {
            $("#user_deactivate_account_button").prop("disabled", true);
            $deactivate_account_container.addClass("disabled_setting_tooltip");
        } else {
            $("#user_deactivate_account_button").prop("disabled", false);
            $deactivate_account_container.removeClass("disabled_setting_tooltip");
        }
    }
}

export function update_send_read_receipts_tooltip() {
    if (realm.realm_enable_read_receipts) {
        $("#send_read_receipts_label .settings-info-icon").hide();
    } else {
        $("#send_read_receipts_label .settings-info-icon").show();
    }
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

    const $spinner_element = $(
        `.custom_user_field[data-field-id="${CSS.escape(field_id)}"] .custom-field-status`,
    ).expectOne();
    settings_ui.do_settings_change(
        method,
        "/json/users/me/profile_data",
        {data: JSON.stringify([field])},
        $spinner_element,
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

function update_user_type_field(field, pills) {
    const user_ids = user_pill.get_user_ids(pills);
    if (user_ids.length < 1) {
        update_user_custom_profile_fields([field.id], channel.del);
    } else {
        update_user_custom_profile_fields([{id: field.id, value: user_ids}], channel.patch);
    }
}

export function add_custom_profile_fields_to_settings() {
    if (!overlays.settings_open()) {
        return;
    }

    const element_id = "#profile-settings .custom-profile-fields-form";
    $(element_id).empty();

    const pill_update_handler = (field, pills) => update_user_type_field(field, pills);

    custom_profile_fields_ui.append_custom_profile_fields(element_id, people.my_current_user_id());
    custom_profile_fields_ui.initialize_custom_user_type_fields(
        element_id,
        people.my_current_user_id(),
        true,
        pill_update_handler,
    );
    custom_profile_fields_ui.initialize_custom_date_type_fields(element_id);
    custom_profile_fields_ui.initialize_custom_pronouns_type_fields(element_id);
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

        if (realm.realm_password_auth_enabled === false) {
            // Skip the password prompt step, since the user doesn't have one.
            request_api_key({});
        } else {
            $("#get_api_key_button").on("click", (e) => {
                e.preventDefault();
                e.stopPropagation();
                do_get_api_key();
            });
            $("#get_api_key_password").on("keydown", (e) => {
                if (keydown_util.is_enter_event(e)) {
                    e.preventDefault();
                    e.stopPropagation();
                    do_get_api_key();
                }
            });
        }

        $("#regenerate_api_key").on("click", (e) => {
            const email = current_user.delivery_email;
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
                    if (xhr.responseJSON?.msg) {
                        $("#user_api_key_error").text(xhr.responseJSON.msg).show();
                    }
                },
            });
            e.preventDefault();
            e.stopPropagation();
        });

        $("#download_zuliprc").on("click", function () {
            const bot_object = {
                user_id: people.my_current_user_id(),
                email: current_user.delivery_email,
                api_key: $("#api_key_value").text(),
            };
            const data = settings_bots.generate_zuliprc_content(bot_object);
            $(this).attr("href", settings_bots.encode_zuliprc_as_url(data));
        });

        $("#api_key_modal [data-micromodal-close]").on("click", () => {
            common.reset_password_toggle_icons(
                "#get_api_key_password",
                "#get_api_key_password + .password_visibility_toggle",
            );
        });
    };

    $("#api_key_button").on("click", (e) => {
        $("body").append($(render_settings_api_key_modal()));
        setup_api_key_modal();
        $("#api_key_status").hide();
        modals.open("api_key_modal", {
            autoremove: true,
            on_show() {
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

        function validate_input() {
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
            html_body: render_dialog_change_password({
                password_min_length: realm.password_min_length,
                password_min_guesses: realm.password_min_guesses,
            }),
            html_submit_button: $t_html({defaultMessage: "Change"}),
            loading_spinner: true,
            id: "change_password_modal",
            form_id: "change_password_container",
            post_render: change_password_post_render,
            on_click: do_change_password,
            validate_input,
        });

        if (realm.realm_password_auth_enabled !== false) {
            // zxcvbn.js is pretty big, and is only needed on password
            // change, so load it asynchronously.
            password_quality = (await import("./password_quality")).password_quality;
            $("#pw_strength .bar").removeClass("hide");

            $("#new_password").on("input", () => {
                const $field = $("#new_password");
                password_quality($field.val(), $("#pw_strength .bar"), $field);
            });
        }
    });

    function do_change_password() {
        const $change_password_error = $("#change_password_modal").find("#dialog_error");
        $change_password_error.hide();

        const data = {
            old_password: $("#old_password").val(),
            new_password: $("#new_password").val(),
        };

        const $new_pw_field = $("#new_password");
        const new_pw = data.new_password;
        if (new_pw !== "") {
            if (password_quality === undefined) {
                // password_quality didn't load, for whatever reason.
                settings_change_error(
                    "An internal error occurred; try reloading the page. " +
                        "Sorry for the trouble!",
                );
                return;
            } else if (!password_quality(new_pw, undefined, $new_pw_field)) {
                settings_change_error($t_html({defaultMessage: "New password is too weak"}));
                return;
            }
        }

        channel.set_password_change_in_progress(true);
        const opts = {
            success_continuation() {
                channel.set_password_change_in_progress(false);
                dialog_widget.close();
            },
            error_continuation() {
                dialog_widget.hide_dialog_spinner();
                channel.set_password_change_in_progress(false);
            },
            $error_msg_element: $change_password_error,
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

    function do_change_email() {
        const $change_email_error = $("#change_email_modal").find("#dialog_error");
        const data = {};
        data.email = $("#change_email_form").find("input[name='email']").val();

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
                dialog_widget.close();
            },
            error_continuation() {
                dialog_widget.hide_dialog_spinner();
            },
            $error_msg_element: $change_email_error,
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

    $("#change_email_button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (settings_data.user_can_change_email()) {
            dialog_widget.launch({
                html_heading: $t_html({defaultMessage: "Change email"}),
                html_body: render_change_email_modal({delivery_email: current_user.delivery_email}),
                html_submit_button: $t_html({defaultMessage: "Change"}),
                loading_spinner: true,
                id: "change_email_modal",
                form_id: "change_email_form",
                on_click: do_change_email,
                on_shown() {
                    ui_util.place_caret_at_end($("#change_email_form input")[0]);
                },
                update_submit_disabled_state_on_change: true,
            });
        }
    });

    function do_demo_organization_add_email(e) {
        e.preventDefault();
        e.stopPropagation();
        const $change_email_error = $("#demo_organization_add_email_modal").find("#dialog_error");
        const data = {};
        data.email = $("#demo_organization_add_email").val();
        data.full_name = $("#demo_organization_update_full_name").val();

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
                dialog_widget.close();
            },
            error_continuation() {
                dialog_widget.hide_dialog_spinner();
            },
            $error_msg_element: $change_email_error,
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

    $("#demo_organization_add_email_button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();

        function demo_organization_add_email_post_render() {
            // Disable submit button if either input is an empty string.
            const $add_email_element = $("#demo_organization_add_email");
            const $add_name_element = $("#demo_organization_update_full_name");

            const $demo_organization_submit_button = $(
                "#demo_organization_add_email_modal .dialog_submit_button",
            );
            $demo_organization_submit_button.prop("disabled", true);

            $("#demo_organization_add_email_form input").on("input", () => {
                $demo_organization_submit_button.prop(
                    "disabled",
                    $add_email_element.val().trim() === "" || $add_name_element.val().trim() === "",
                );
            });
        }

        if (
            realm.demo_organization_scheduled_deletion_date &&
            current_user.is_owner &&
            current_user.delivery_email === ""
        ) {
            dialog_widget.launch({
                html_heading: $t_html({defaultMessage: "Add email"}),
                html_body: render_demo_organization_add_email_modal({
                    delivery_email: current_user.delivery_email,
                    full_name: current_user.full_name,
                }),
                html_submit_button: $t_html({defaultMessage: "Add"}),
                loading_spinner: true,
                id: "demo_organization_add_email_modal",
                form_id: "demo_organization_add_email_form",
                on_click: do_demo_organization_add_email,
                on_shown() {
                    ui_util.place_caret_at_end($("#demo_organization_add_email_form input")[0]);
                },
                post_render: demo_organization_add_email_post_render,
            });
        }
    });

    $("#profile-settings").on("click", ".custom_user_field .remove_date", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const $field = $(e.target).closest(".custom_user_field").expectOne();
        const field_id = Number.parseInt($field.attr("data-field-id"), 10);
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

    $("#account-settings .deactivate_realm_button").on(
        "click",
        settings_org.deactivate_organization,
    );
    $("#user_deactivate_account_button").on("click", (e) => {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active` in `settings.js`.
        e.preventDefault();
        e.stopPropagation();

        function handle_confirm() {
            channel.del({
                url: "/json/users/me",
                success() {
                    dialog_widget.hide_dialog_spinner();
                    dialog_widget.close();
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
                                `<a target="_blank" href="/#organization/organization-profile">${content_html.join(
                                    "",
                                )}</a>`,
                        },
                    );
                    let rendered_error_msg;
                    if (xhr.responseJSON?.code === "CANNOT_DEACTIVATE_LAST_USER") {
                        if (xhr.responseJSON.is_last_owner) {
                            rendered_error_msg = error_last_owner;
                        } else {
                            rendered_error_msg = error_last_user;
                        }
                    }
                    dialog_widget.hide_dialog_spinner();
                    dialog_widget.close();
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

    $("#show_my_user_profile_modal").on("click", (e) => {
        e.stopPropagation();
        e.preventDefault();

        const user = people.get_by_user_id(people.my_current_user_id());
        user_profile.show_user_profile(user);
    });

    // When the personal settings overlay is opened, we reset
    // the tracking variable for live update behavior of the
    // user avatar upload widget and handlers.
    user_avatar_widget_created = false;

    if (settings_data.user_can_change_avatar()) {
        avatar.build_user_avatar_widget(upload_avatar);
        user_avatar_widget_created = true;
    }

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

        const $input_elem = $(e.currentTarget);
        const setting_name = $input_elem.attr("name");
        const checked = $input_elem.prop("checked");

        const data = {[setting_name]: checked};
        settings_ui.do_settings_change(
            channel.patch,
            "/json/settings",
            data,
            $("#account-settings .privacy-setting-status").expectOne(),
        );
    });

    $("#user_email_address_visibility").val(user_settings.email_address_visibility);

    $("#user_email_address_visibility").on("change", function (e) {
        e.preventDefault();
        e.stopPropagation();

        const data = {email_address_visibility: this.value};

        settings_ui.do_settings_change(
            channel.patch,
            "/json/settings",
            data,
            $("#account-settings .privacy-setting-status").expectOne(),
        );
    });
}
