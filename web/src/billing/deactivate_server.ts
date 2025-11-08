import $ from "jquery";

export function initialize(): void {
    $("#server-deactivate-form").validate({
        submitHandler(form) {
            $("#server-deactivate-form").find(".loader").css("display", "inline-block");
            $("#server-deactivate-button .server-deactivate-button-text").hide();

            form.submit();
        },
    });
}

$(() => {
    initialize();
});
