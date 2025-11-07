import $ from "jquery";

export function initialize(): void {
    $("#server-deactivate-form").validate({
        submitHandler(form) {
            $("#server-deactivate-form").find(".loader").show();
            $("#server-deactivate-button .server-deactivate-button-text").hide();

            form.submit();
        },
    });
}

$(() => {
    initialize();
});
