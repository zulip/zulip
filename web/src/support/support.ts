import ClipboardJS from "clipboard";
import $ from "jquery";
import assert from "minimalistic-assert";

$(() => {
    $("body").on("click", "button.scrub-realm-button", function (this: HTMLButtonElement, e) {
        e.preventDefault();
        const message =
            "Confirm the string_id of the realm you want to scrub.\n\n WARNING! This action is irreversible!";
        const actual_string_id = $(this).attr("data-string-id");
        // eslint-disable-next-line no-alert
        const confirmed_string_id = window.prompt(message);
        if (confirmed_string_id === actual_string_id) {
            assert(this.form !== null);
            this.form.submit();
        } else {
            // eslint-disable-next-line no-alert
            window.alert("The string_id you entered is not correct. Aborted.");
        }
    });

    $("body").on("click", "button.delete-user-button", function (this: HTMLButtonElement, e) {
        e.preventDefault();
        const message =
            "Confirm the email of the user you want to delete.\n\n WARNING! This action is irreversible!";
        const actual_email = $(this).attr("data-email");
        // eslint-disable-next-line no-alert
        const confirmed_email = window.prompt(message);
        if (confirmed_email === actual_email) {
            const actual_string_id = $(this).attr("data-string-id");
            // eslint-disable-next-line no-alert
            const confirmed_string_id = window.prompt(
                "Now provide string_id of the realm to confirm.",
            );
            if (confirmed_string_id === actual_string_id) {
                assert(this.form !== null);
                this.form.submit();
            } else {
                // eslint-disable-next-line no-alert
                window.alert("The string_id you entered is not correct. Aborted.");
            }
        } else {
            // eslint-disable-next-line no-alert
            window.alert("The email you entered is not correct. Aborted.");
        }
    });

    new ClipboardJS("a.copy-button");
});
