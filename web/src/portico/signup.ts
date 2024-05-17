import $ from "jquery";
import assert from "minimalistic-assert";
import {z} from "zod";

import * as common from "../common";
import {$t} from "../i18n";
import {password_quality, password_warning} from "../password_quality";
import * as settings_config from "../settings_config";

import * as portico_modals from "./portico_modals";

$(() => {
    // NB: this file is included on multiple pages.  In each context,
    // some of the jQuery selectors below will return empty lists.

    const $password_field = $<HTMLInputElement>("input#id_password, input#id_new_password1");
    if ($password_field.length > 0) {
        $.validator.addMethod(
            "password_strength",
            (value: string) => password_quality(value, undefined, $password_field),
            () => password_warning($password_field.val()!, $password_field),
        );
        // Reset the state of the password strength bar if the page
        // was just reloaded due to a validation failure on the backend.
        password_quality($password_field.val()!, $("#pw_strength .bar"), $password_field);

        $password_field.on("input", function () {
            // Update the password strength bar even if we aren't validating
            // the field yet.
            password_quality($(this).val()!, $("#pw_strength .bar"), $(this));
        });
    }

    common.setup_password_visibility_toggle(
        "#ldap-password",
        "#ldap-password ~ .password_visibility_toggle",
    );
    common.setup_password_visibility_toggle(
        "#id_password",
        "#id_password ~ .password_visibility_toggle",
    );
    common.setup_password_visibility_toggle(
        "#id_new_password1",
        "#id_new_password1 ~ .password_visibility_toggle",
    );
    common.setup_password_visibility_toggle(
        "#id_new_password2",
        "#id_new_password2 ~ .password_visibility_toggle",
    );

    $("#registration, #password_reset, #create_realm").validate({
        rules: {
            password: "password_strength",
            new_password1: "password_strength",
        },
        errorElement: "p",
        errorPlacement($error: JQuery, $element: JQuery) {
            // NB: this is called at most once, when the error element
            // is created.
            $element.next(".help-inline.alert.alert-error").remove();
            if ($element.next().is(`label[for="${$element.attr("id")!}"]`)) {
                $error.insertAfter($element.next()).addClass("help-inline alert alert-error");
            } else if ($element.parent().is(`label[for="${$element.attr("id")!}"]`)) {
                // For checkboxes and radio-buttons
                $error.insertAfter($element.parent()).addClass("help-inline alert alert-error");
            } else {
                $error.insertAfter($element).addClass("help-inline alert alert-error");
            }
        },
    });

    if ($("#registration").length > 0) {
        // Check if there is no input field with errors.
        if ($(".help-inline:not(:empty)").length === 0) {
            // Find the first input field present in the form that is
            // not hidden and disabled and store it in a variable.
            const $firstInputElement = $("input:not(:hidden, :disabled)").first();
            // Focus on the first input field in the form.
            $firstInputElement.trigger("focus");
            // Override the automatic scroll to the focused
            // element. On the (tall) new organization form, at least,
            // this avoids scrolling to the middle of the page (past
            // the organization details section).
            $("html").scrollTop(0);
        } else {
            // If input field with errors is present.
            // Find the input field having errors and stores it in a variable.
            const $inputElementWithError = $(".help-inline:not(:empty)")
                .first()
                .parent()
                .find("input");
            // Focus on the input field having errors.
            $inputElementWithError.trigger("focus");
        }

        // reset error message displays
        $("#id_team_subdomain_error_client").css("display", "none");
        if ($(".team_subdomain_error_server").text() === "") {
            $(".team_subdomain_error_server").css("display", "none");
        }

        $("#timezone").val(new Intl.DateTimeFormat().resolvedOptions().timeZone);
    }

    $("#registration").on("submit", () => {
        if ($("#registration").valid()) {
            $(".register-button .loader").css("display", "inline-block");
            $(".register-button").prop("disabled", true);
            $(".register-button span").hide();
        }
    });

    // Code in this block will be executed when the /accounts/send_confirm/
    // endpoint is visited i.e. accounts_send_confirm.html is rendered.
    if ($("[data-page-id='accounts-send-confirm']").length > 0) {
        $("#resend_email_link").on("click", () => {
            $(".resend_confirm").trigger("submit");
        });
    }

    // Code in this block will be executed when the user visits /register
    // i.e. accounts_home.html is rendered.
    if ($("[data-page-id='accounts-home']").length > 0 && window.location.hash.startsWith("#")) {
        document.querySelector<HTMLFormElement>("#send_form")!.action += window.location.hash;
    }

    // Code in this block will be executed when the user is at login page
    // i.e. login.html is rendered.
    if ($("[data-page-id='login-page']").length > 0 && window.location.hash.startsWith("#")) {
        // All next inputs have the same value when the page is
        // rendered, so it's OK that this selector gets N elements.
        const next_value = $("input[name='next']").attr("value");

        // We need to add `window.location.hash` to the `next`
        // property, since the server doesn't receive URL fragments
        // (and thus could not have included them when rendering a
        // redirect to this page).
        $("input[name='next']").attr("value", `${next_value!}${window.location.hash}`);
    }

    $("#send_confirm").validate({
        errorElement: "div",
        errorPlacement($error: JQuery) {
            $(".email-frontend-error").empty();
            $("#send_confirm .alert.email-backend-error").remove();
            $error.appendTo($(".email-frontend-error")).addClass("text-error");
        },
        success() {
            $("#errors").empty();
        },
    });

    $<HTMLInputElement>(".register-page input#email, .login-page-container input#id_username").on(
        "focusout keydown",
        function (e) {
            // check if it is the "focusout" or if it is a keydown, then check if
            // the keycode was the one for "Enter".
            if (e.type === "focusout" || e.key === "Enter") {
                $(this).val($(this).val()!.trim());
            }
        },
    );

    const show_subdomain_section = function (bool: boolean): void {
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
            this.defaultShowErrors!();
        },
    });

    function check_subdomain_available(subdomain: string): void {
        const url = "/json/realm/subdomain/" + subdomain;
        void $.get(url, (response) => {
            const {msg} = z.object({msg: z.string()}).parse(response);
            if (msg !== "available") {
                $("#id_team_subdomain_error_client").html(msg);
                $("#id_team_subdomain_error_client").show();
            }
        });
    }

    function update_full_name_section(): void {
        if ($("#source_realm_select").length && $("#source_realm_select").val() !== "") {
            $("#full_name_input_section").hide();
            $("#profile_info_section").show();
            const avatar_url = $($("#source_realm_select").prop("selectedOptions")).attr(
                "data-avatar",
            );
            const full_name = $($("#source_realm_select").prop("selectedOptions")).attr(
                "data-full-name",
            );
            $("#profile_full_name").text(full_name!);
            $("#id_full_name").val(full_name!);
            $("#profile_avatar").attr("src", avatar_url!);
        } else {
            $("#full_name_input_section").show();
            $("#profile_info_section").hide();
        }
    }

    $("#source_realm_select").on("change", update_full_name_section);
    update_full_name_section();

    let timer: number;
    $("#id_team_subdomain").on("input", () => {
        $(".team_subdomain_error_server").text("").css("display", "none");
        $("#id_team_subdomain_error_client").css("display", "none");
        clearTimeout(timer);
        timer = setTimeout(check_subdomain_available, 250, $("#id_team_subdomain").val());
    });

    // GitHub auth
    $("body").on("click", "#choose_email .choose-email-box", function (this: HTMLElement) {
        assert(this.parentElement instanceof HTMLFormElement);
        this.parentElement.submit();
    });

    $("#new-user-email-address-visibility .change_email_address_visibility").on("click", () => {
        portico_modals.open("change-email-address-visibility-modal");
    });

    $("#change-email-address-visibility-modal .dialog_submit_button").on("click", () => {
        const selected_val = Number.parseInt(
            $<HTMLSelectElement & {type: "select-one"}>(
                "select:not([multiple])#new_user_email_address_visibility",
            ).val()!,
            10,
        );
        $("#email_address_visibility").val(selected_val);
        portico_modals.close("change-email-address-visibility-modal");

        let selected_option_text;

        // These strings should be consistent with those defined for the same element in
        // 'templates/zerver/register.html'.
        switch (selected_val) {
            case settings_config.email_address_visibility_values.admins_only.code: {
                selected_option_text = $t({
                    defaultMessage:
                        "Administrators of this Zulip organization will be able to see this email address.",
                });

                break;
            }
            case settings_config.email_address_visibility_values.moderators.code: {
                selected_option_text = $t({
                    defaultMessage:
                        "Administrators and moderators this Zulip organization will be able to see this email address.",
                });

                break;
            }
            case settings_config.email_address_visibility_values.nobody.code: {
                selected_option_text = $t({
                    defaultMessage:
                        "Nobody in this Zulip organization will be able to see this email address.",
                });

                break;
            }
            default: {
                selected_option_text = $t({
                    defaultMessage:
                        "Other users in this Zulip organization will be able to see this email address.",
                });
            }
        }
        $("#new-user-email-address-visibility .current-selected-option").text(selected_option_text);
    });

    $("#registration").on("click keypress", ".edit-realm-details", (e) => {
        if (e.type === "keypress" && e.key !== "Enter") {
            return;
        }

        $("#registration .not-editable-realm-details").addClass("hide");
        $("#registration .realm-creation-editable-inputs").removeClass("hide");
        $("#id_team_name").trigger("focus");
        // This is a hack to have cursor at end after focussing the input.
        const name_val = $("#id_team_name").val()!;
        $("#id_team_name").val("").val(name_val);

        $(e.target).hide();
    });

    $("#how-realm-creator-found-zulip select").on("change", function () {
        const elements: Record<string, string> = {
            Other: "how-realm-creator-found-zulip-other",
            Advertisement: "how-realm-creator-found-zulip-where-ad",
            "At an organization that's using it":
                "how-realm-creator-found-zulip-which-organization",
        };

        const hideElement = (element: string): void => {
            const $element = $(`#${element}`);
            $element.hide();
            $element.removeAttr("required");
            $(`#${element}-error`).hide();
        };

        const showElement = (element: string): void => {
            const $element = $(`#${element}`);
            $element.show();
            $element.attr("required", "required");
        };

        // Reset state
        for (const element of Object.values(elements)) {
            if (element) {
                hideElement(element);
            }
        }

        // Show the additional input box if needed.
        const selected_option = $("option:selected", this).text();
        const selected_element = elements[selected_option];
        if (selected_element) {
            showElement(selected_element);
        }
    });
});
