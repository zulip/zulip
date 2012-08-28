import ClipboardJS from "clipboard";
import $ from "jquery";
import assert from "minimalistic-assert";

function initialize(): void {
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

    $("body").on(
        "blur",
        "input[name='monthly_discounted_price']",
        function (this: HTMLInputElement, _event: JQuery.Event) {
            const input_monthly_price = $(this).val();
            if (!input_monthly_price) {
                return;
            }
            const monthly_price = Number.parseInt(input_monthly_price, 10);
            const $annual_price = $(this).siblings("input[name='annual_discounted_price']");
            // Update the annual price input if it's empty
            if (!$annual_price.val()) {
                const data_original_monthly_price = $(this).attr("data-original-monthly-price");
                const data_original_annual_price = $annual_price.attr("data-original-annual-price");
                if (data_original_monthly_price && data_original_annual_price) {
                    const original_monthly_price = Number.parseInt(data_original_monthly_price, 10);
                    const original_annual_price = Number.parseInt(data_original_annual_price, 10);
                    let derived_annual_price =
                        (original_annual_price / original_monthly_price) * monthly_price;
                    derived_annual_price = Math.round(derived_annual_price);
                    $annual_price.val(derived_annual_price);
                }
            }
        },
    );

    $("body").on(
        "blur",
        "input[name='annual_discounted_price']",
        function (this: HTMLInputElement, _event: JQuery.Event) {
            const input_annual_price = $(this).val();
            if (!input_annual_price) {
                return;
            }
            const annual_price = Number.parseInt(input_annual_price, 10);
            const $monthly_price = $(this).siblings("input[name='monthly_discounted_price']");
            // Update the monthly price input if it's empty
            if (!$monthly_price.val()) {
                const data_original_monthly_price = $monthly_price.attr(
                    "data-original-monthly-price",
                );
                const data_original_annual_price = $(this).attr("data-original-annual-price");
                if (data_original_monthly_price && data_original_annual_price) {
                    const original_monthly_price = Number.parseInt(data_original_monthly_price, 10);
                    const original_annual_price = Number.parseInt(data_original_annual_price, 10);
                    let derived_monthly_price =
                        (original_monthly_price / original_annual_price) * annual_price;
                    derived_monthly_price = Math.round(derived_monthly_price);
                    $monthly_price.val(derived_monthly_price);
                }
            }
        },
    );
}

initialize();
