$(function () {
    // NB: this file is included on multiple pages.  In each context,
    // some of the jQuery selectors below will return empty lists.
    var password_field = $('#id_password, #id_new_password1');

    $.validator.addMethod('password_strength', function (value) {
        return common.password_quality(value, undefined, password_field);
    }, function () {
        return common.password_warning(password_field.val(), password_field);
    });

    function highlight(class_to_add) {
        // Set a class on the enclosing control group.
        return function (element) {
            $(element).closest('.control-group')
                .removeClass('success error')
                .addClass(class_to_add);
        };
    }

    $('#registration, #password_reset').validate({
        rules: {
            password:      'password_strength',
            new_password1: 'password_strength',
        },
        errorElement: "p",
        errorPlacement: function (error, element) {
            // NB: this is called at most once, when the error element
            // is created.
            element.next('.help-inline.text-error').remove();
            if (element.next().is('label[for="' + element.attr('id') + '"]')) {
                error.insertAfter(element.next()).addClass('help-inline text-error');
            } else {
                error.insertAfter(element).addClass('help-inline text-error');
            }
        },
        highlight:   highlight('error'),
        unhighlight: highlight('success'),
    });

    password_field.on('change keyup', function () {
        // Update the password strength bar even if we aren't validating
        // the field yet.
        common.password_quality($(this).val(), $('#pw_strength .bar'), $(this));
    });

    $("#send_confirm").validate({
        errorElement: "div",
        errorPlacement: function (error) {
            $('.alert-error').empty();
            error.appendTo(".alert-error")
                 .addClass("text-error");
        },
        success: function () {
            $('#errors').empty();
        },
    });

    $("#login_form").validate({
        errorClass: "text-error",
        wrapper: "div",
    });
});
