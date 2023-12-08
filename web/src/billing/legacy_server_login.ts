import $ from "jquery";

export function initialize(): void {
    $("#server-login-form, #server-confirm-login-form").validate({
        errorClass: "text-error",
        wrapper: "div",
        submitHandler(form) {
            $("#server-login-form").find(".loader").css("display", "inline-block");
            $("#server-login-button .server-login-button-text").hide();
            $("#server-confirm-login-form").find(".loader").css("display", "inline-block");
            $("#server-confirm-login-button .server-login-button-text").hide();

            form.submit();
        },
        invalidHandler() {
            // this removes all previous errors that were put on screen
            // by the server.
            $("#server-login-form .alert.alert-error").remove();
            $("#server-confirm-login-form .alert.alert-error").remove();
        },
        showErrors(error_map) {
            if (error_map.password) {
                $("#server-login-form .alert.alert-error").remove();
                $("#server-confirm-login-form .alert.alert-error").remove();
            }
            this.defaultShowErrors!();
        },
    });
}

$(() => {
    initialize();
});
