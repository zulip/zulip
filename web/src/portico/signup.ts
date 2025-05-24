import $ from "jquery";
import "jquery-validation";
import _ from "lodash";
import { z } from "zod";
import { password_quality, password_warning } from "../password_quality";
import * as common from "../common";
import * as settings_config from "../settings_config";
import { $t } from "../i18n";
import * as portico_modals from "./portico_modals";

declare global {
    interface JQuery {
        validate(options?: any): JQueryValidation.Validation;
        valid(): boolean;
    }

    interface JQueryStatic {
        validator: JQueryValidation.Validation;
    }

    namespace JQueryValidation {
        interface Validation {
            addMethod(
                name: string,
                method: (value: string, element: HTMLElement) => boolean,
                message?: string | (() => string)
            ): void;
        }
    }
}

$(() => {
    const $password_field = $<HTMLInputElement>("input#id_password, input#id_new_password1");

    if ($password_field.length > 0) {
       $.validator.addMethod(
            "password_strength",
            (value: string) => password_quality(value, undefined, $password_field),
            () => password_warning($password_field.val()!, $password_field)
        );
        password_quality($password_field.val()!, $("#pw_strength .bar"), $password_field);

        const debounced_password_quality = _.debounce((password: string, $field: JQuery) => {
            password_quality(password, $("#pw_strength .bar"), $field);
        }, 300);

        $password_field.on("input", function () {
            const password = $(this).val()!;
            if (password.length > 30) {
                debounced_password_quality(password, $(this));
            } else {
                debounced_password_quality.cancel();
                password_quality(password, $("#pw_strength .bar"), $(this));
            }
        });
    }

    common.setup_password_visibility_toggle("#id_password", "#id_password ~ .password_visibility_toggle");
    common.setup_password_visibility_toggle("#id_new_password1", "#id_new_password1 ~ .password_visibility_toggle");
    common.setup_password_visibility_toggle("#id_new_password2", "#id_new_password2 ~ .password_visibility_toggle");

    // ✅ jQuery Validation with TypeScript-safe workaround
    const validator = ($("#registration") as any).validate({
        rules: {
            password: {
                password_strength: {
                    depends: (element: HTMLElement): boolean => element.id !== "ldap-password",
                },
            },
            new_password1: "password_strength",
            email: {
                required: true,
                email: true,
            },
            full_name: {
                required: true,
            },
        },
        errorElement: "p",
        errorPlacement($error: JQuery, $element: JQuery) {
            $element.next(".help-inline.alert.alert-error").remove();
            $error.insertAfter($element).addClass("help-inline alert alert-error");
        },
    });

    if ($("#registration").length > 0) {
        if ($(".help-inline:not(:empty)").length === 0) {
            $("input:not([type=hidden], :disabled)").first().trigger("focus");
            $("html").scrollTop(0);
        } else {
            $(".help-inline:not(:empty)").first().parent().find("input").trigger("focus");
        }
        $("#timezone").val(new Intl.DateTimeFormat().resolvedOptions().timeZone);
    }

    $("#registration").on("submit", () => {
        if (($("#registration") as any).valid()) {
            $(".register-button .loader").css("display", "inline-block");
            $(".register-button").prop("disabled", true);
            $(".register-button span").hide();
        }
    });

    const altcha = document.querySelector<HTMLElement & { configure?: Function }>("altcha-widget");
    if (altcha && typeof altcha.configure === "function") {
        altcha.configure({
            auto: "onload",
            async customfetch(url: string, init?: RequestInit) {
                return fetch(url, { ...init, credentials: "include" });
            },
        });

        const $submit = $(altcha).closest("form").find("button[type=submit]");
        $submit.prop("disabled", true);

        altcha.addEventListener("statechange", (ev: any) => {
            if (ev.detail.state === "verified") {
                $submit.prop("disabled", false);
            }
        });
    }

    const update_full_name_section = () => {
        const $select = $("#source_realm_select");
        const selectedOption = $select.prop("selectedOptions")?.[0];
        if (selectedOption && $select.val() !== "") {
            $("#full_name_input_section").hide();
            $("#profile_info_section").show();
            $("#profile_full_name").text($(selectedOption).attr("data-full-name")!);
            $("#id_full_name").val($(selectedOption).attr("data-full-name")!);
            $("#profile_avatar").attr("src", $(selectedOption).attr("data-avatar")!);
        } else {
            $("#full_name_input_section").show();
            $("#profile_info_section").hide();
        }
    };

    $("#source_realm_select").on("change", update_full_name_section);
    update_full_name_section();

    const show_subdomain_section = (isChecked: boolean) => {
        $("#subdomain_section")[isChecked ? "hide" : "show"]();
    };
    $("#realm_in_root_domain").on("change", function () {
        show_subdomain_section($(this).is(":checked"));
    });

     let timer: ReturnType<typeof setTimeout>;
    $("#id_team_subdomain").on("input", () => {
        $(".team_subdomain_error_server").text("").hide();
        $("#id_team_subdomain_error_client").hide();
        clearTimeout(timer);
        timer = setTimeout(() => {
            const subdomain = $("#id_team_subdomain").val();
            $.get(`/json/realm/subdomain/${subdomain}`, (response) => {
                const { msg } = z.object({ msg: z.string() }).parse(response);
                if (msg !== "available") {
                    $("#id_team_subdomain_error_client").html(msg).show();
                }
            });
        }, 250);
    });

    $("#new-user-email-address-visibility .change_email_address_visibility").on("click", () => {
        portico_modals.open("change-email-address-visibility-modal");
    });

    $("#change-email-address-visibility-modal .dialog_submit_button").on("click", () => {
        const selected_val = parseInt(
            $("select#new_user_email_address_visibility").val()!.toString(), 10,
        );
        $("#email_address_visibility").val(selected_val);
        portico_modals.close("change-email-address-visibility-modal");

        let selected_option_text;
        switch (selected_val) {
            case settings_config.email_address_visibility_values.admins_only.code:
                selected_option_text = $t({ defaultMessage: "Only administrators can see your email address." });
                break;
            case settings_config.email_address_visibility_values.moderators.code:
                selected_option_text = $t({ defaultMessage: "Admins and moderators can see your email address." });
                break;
            case settings_config.email_address_visibility_values.nobody.code:
                selected_option_text = $t({ defaultMessage: "No one can see your email address." });
                break;
            default:
                selected_option_text = $t({ defaultMessage: "Other users can see your email address." });
        }
        $("#new-user-email-address-visibility .current-selected-option").text(selected_option_text);
    });
});
