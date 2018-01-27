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
            element.next('.help-inline.alert.alert-error').remove();
            if (element.next().is('label[for="' + element.attr('id') + '"]')) {
                error.insertAfter(element.next()).addClass('help-inline alert alert-error');
            } else {
                error.insertAfter(element).addClass('help-inline alert alert-error');
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

    $("#login_form").submit(function () {
        $('.spinner').show();
        document.getElementById('login_button').innerHTML = 'Signing in ...';
    });

    $("#login_form").validate({
        errorClass: "text-error",
        wrapper: "div",
    });

    $(".register-page #email, .login-page-container #id_username").on('focusout keydown', function (e) {
        // check if it is the "focusout" or if it is a keydown, then check if
        // the keycode was the one for "enter" (13).
        if (e.type === "focusout" || e.which === 13) {
            $(this).val($.trim($(this).val()));
        }
    });

    var show_subdomain_section = function (bool) {
        var action = bool ? "hide" : "show";
        $("#subdomain_section")[action]();
    };

    $("#realm_in_root_domain").change(function () {
        show_subdomain_section($(this).is(":checked"));
    });
});
