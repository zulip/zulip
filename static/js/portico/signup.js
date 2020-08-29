"use strict";

const moment = require("moment-timezone");

$(() => {
    // NB: this file is included on multiple pages.  In each context,
    // some of the jQuery selectors below will return empty lists.

    const password_field = $("#id_password, #id_new_password1");
    if (password_field.length > 0) {
        $.validator.addMethod(
            "password_strength",
            (value) => common.password_quality(value, undefined, password_field),
            () => common.password_warning(password_field.val(), password_field),
        );
        // Reset the state of the password strength bar if the page
        // was just reloaded due to a validation failure on the backend.
        common.password_quality(password_field.val(), $("#pw_strength .bar"), password_field);

        password_field.on("input", function () {
            // Update the password strength bar even if we aren't validating
            // the field yet.
            common.password_quality($(this).val(), $("#pw_strength .bar"), $(this));
        });
    }

    function highlight(class_to_add) {
        // Set a class on the enclosing control group.
        return function (element) {
            $(element)
                .closest(".control-group")
                .removeClass("success error")
                .addClass(class_to_add);
        };
    }

    $("#registration, #password_reset").validate({
        rules: {
            password: "password_strength",
            new_password1: "password_strength",
        },
        errorElement: "p",
        errorPlacement(error, element) {
            // NB: this is called at most once, when the error element
            // is created.
            element.next(".help-inline.alert.alert-error").remove();
            if (element.next().is('label[for="' + element.attr("id") + '"]')) {
                error.insertAfter(element.next()).addClass("help-inline alert alert-error");
            } else if (element.parent().is('label[for="' + element.attr("id") + '"]')) {
                // For checkboxes and radio-buttons
                error.insertAfter(element.parent()).addClass("help-inline alert alert-error");
            } else {
                error.insertAfter(element).addClass("help-inline alert alert-error");
            }
        },
        highlight: highlight("error"),
        unhighlight: highlight("success"),
    });

    if ($("#registration").length > 0) {
        // Check if there is no input field with errors.
        if ($(".help-inline:not(:empty)").length === 0) {
            // Find the first input field present in the form that is
            // not hidden and disabled and store it in a variable.
            const firstInputElement = $("input:not(:hidden, :disabled)").first();
            // Focus on the first input field in the form.
            common.autofocus(firstInputElement);
        } else {
            // If input field with errors is present.
            // Find the input field having errors and stores it in a variable.
            const inputElementWithError = $(".help-inline:not(:empty)")
                .first()
                .parent()
                .find("input");
            // Focus on the input field having errors.
            common.autofocus(inputElementWithError);
        }

        // reset error message displays
        $("#id_team_subdomain_error_client").css("display", "none");
        if ($(".team_subdomain_error_server").text() === "") {
            $(".team_subdomain_error_server").css("display", "none");
        }

        $("#timezone").val(moment.tz.guess());
    }

    // Code in this block will be executed when the /accounts/send_confirm
    // endpoint is visited i.e. accounts_send_confirm.html is rendered.
    if ($("[data-page-id='accounts-send-confirm']").length > 0) {
        $("#resend_email_link").on("click", () => {
            $(".resend_confirm").trigger("submit");
        });
    }

    // Code in this block will be executed when the user visits /register
    // i.e. accounts_home.html is rendered.
    if ($("[data-page-id='accounts-home']").length > 0) {
        if (window.location.hash.substring(0, 1) === "#") {
            document.email_form.action += window.location.hash;
        }
    }

    // Code in this block will be executed when the user is at login page
    // i.e. login.html is rendered.
    if ($("[data-page-id='login-page']").length > 0) {
        if (window.location.hash.substring(0, 1) === "#") {
            /* We append the location.hash to the formaction so that URL can be
            preserved after user is logged in. See this:
            https://stackoverflow.com/questions/5283395/url-hash-is-persisting-between-redirects */
            const email_formaction = $("#login_form").attr("action");
            $("#login_form").attr("action", email_formaction + "/" + window.location.hash);
            $(".social_login_form input[name='next']").attr("value", "/" + window.location.hash);
        }
    }

    $("#send_confirm").validate({
        errorElement: "div",
        errorPlacement(error) {
            $(".email-frontend-error").empty();
            $("#send_confirm .alert.email-backend-error").remove();
            error.appendTo(".email-frontend-error").addClass("text-error");
        },
        success() {
            $("#errors").empty();
        },
    });

    $(".register-page #email, .login-page-container #id_username").on("focusout keydown", function (
        e,
    ) {
        // check if it is the "focusout" or if it is a keydown, then check if
        // the keycode was the one for "enter" (13).
        if (e.type === "focusout" || e.which === 13) {
            $(this).val($(this).val().trim());
        }
    });

    const show_subdomain_section = function (bool) {
        const action = bool ? "hide" : "show";
        $("#subdomain_section")[action]();
    };

    $("#realm_in_root_domain").on("change", function () {
        show_subdomain_section($(this).is(":checked"));
    });

    $("#login_form").validate({
        errorClass: "text-error",
        wrapper: "div",
        submitHandler(form) {
            $("#login_form").find(".loader").css("display", "inline-block");
            $("#login_form").find("button .text").hide();

            form.submit();
        },
        invalidHandler() {
            // this removes all previous errors that were put on screen
            // by the server.
            $("#login_form .alert.alert-error").remove();
        },
        showErrors(error_map) {
            if (error_map.password) {
                $("#login_form .alert.alert-error").remove();
            }
            this.defaultShowErrors();
        },
    });

    function check_subdomain_avilable(subdomain) {
        const url = "/json/realm/subdomain/" + subdomain;
        $.get(url, (response) => {
            if (response.msg !== "available") {
                $("#id_team_subdomain_error_client").html(response.msg);
                $("#id_team_subdomain_error_client").show();
            }
        });
    }

    function update_full_name_section() {
        if (
            $("#source_realm_select").length &&
            $("#source_realm_select").find(":selected").val() !== "on"
        ) {
            $("#full_name_input_section").hide();
            $("#profile_info_section").show();
            const avatar_url = $("#source_realm_select").find(":selected").attr("data-avatar");
            const full_name = $("#source_realm_select").find(":selected").attr("data-full-name");
            $("#profile_full_name").text(full_name);
            $("#id_full_name").val(full_name);
            $("#profile_avatar").attr("src", avatar_url);
        } else {
            $("#full_name_input_section").show();
            $("#profile_info_section").hide();
        }
    }

    $("#source_realm_select").on("change", update_full_name_section);
    update_full_name_section();

    let timer;
    $("#id_team_subdomain").on("keydown", () => {
        $(".team_subdomain_error_server").text("").css("display", "none");
        $("#id_team_subdomain_error_client").css("display", "none");
        clearTimeout(timer);
    });
    $("#id_team_subdomain").on("keyup", () => {
        clearTimeout(timer);
        timer = setTimeout(check_subdomain_avilable, 250, $("#id_team_subdomain").val());
    });

    // GitHub auth
    $("body").on("click", "#choose_email .choose-email-box", function () {
        this.parentNode.submit();
    });
});
