$(() => {
    $("body").on("click", ".scrub-realm-button", function (e) {
        e.preventDefault();
        const string_id = $(this).data("string-id");
        const message =
            'Do you really want to scrub the realm "' +
            string_id +
            '"? This action is irreversible.';
        // eslint-disable-next-line no-alert
        if (confirm(message)) {
            this.form.submit();
        }
    });

    $("a.copy-button").on("click", function () {
        common.copy_data_attribute_value($(this), "copytext");
    });
});
