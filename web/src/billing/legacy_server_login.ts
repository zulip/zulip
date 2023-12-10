import $ from "jquery";

export function initialize(): void {
    $("#server-login-form, #remote-billing-confirm-email-form").validate({
        errorClass: "text-error",
        wrapper: "div",
        submitHandler(form) {
            $("#server-login-form").find(".loader").css("display", "inline-block");
            $("#server-login-button .server-login-button-text").hide();
            $("#remote-billing-confirm-email-form").find(".loader").css("display", "inline-block");
            $("#remote-billing-confirm-email-button .server-login-button-text").hide();

            form.submit();
        },
        invalidHandler() {
            // this removes all previous errors that were put on screen
            // by the server.
            $("#server-login-form .alert.alert-error").remove();
            $("#remote-billing-confirm-email-form .alert.alert-error").remove();
        },
        showErrors(error_map) {
            if (error_map.password) {
                $("#server-login-form .alert.alert-error").remove();
                $("#remote-billing-confirm-email-form .alert.alert-error").remove();
            }
            this.defaultShowErrors!();
        },
    });
}

$(() => {
    initialize();
});
