"use strict";

$(() => {
    $("body").on("click", ".scrub-realm-button", function (e) {
        e.preventDefault();
        const message =
            "Confirm the string_id of the realm you want to scrub.\n\n WARNING! This action is irreversible!";
        const actual_string_id = $(this).data("string-id");
        // eslint-disable-next-line no-alert
        const confirmed_string_id = window.prompt(message);
        if (confirmed_string_id === actual_string_id) {
            this.form.submit();
        } else {
            // eslint-disable-next-line no-alert
            window.alert("The string_id you entered is not correct. Aborted.");
        }
    });

    $("a.copy-button").on("click", function () {
        common.copy_data_attribute_value($(this), "copytext");
    });
});
