$(function () {
    $("body").on("click", ".scrub-realm-button", function (e) {
        e.preventDefault();
        var string_id = $(this).data("string-id");
        var message = 'Do you really want to scrub the realm "' + string_id + '"? This action is irreversible.';
        if (confirm(message)) { // eslint-disable-line no-alert
            this.form.submit();
        }
    });

    $('a.copy-button').click(function () {
        common.copy_data_attribute_value($(this), "copytext");
    });
});
