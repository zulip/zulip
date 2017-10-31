const Segments = ($parent) => {
    const $segments = $parent.find("[data-stage]");
    const callbacks = {
        change: {},
        validate: {},
    };

    $segments.eq(0).addClass("show");

    $parent.on("click", "[next-stage]", function () {
        const $stage = $(this).closest("[data-stage]");
        const id = $stage.data("stage");

        if (typeof callbacks.validate[id] === "function") {
            let is_valid = false;

            callbacks.validate[id]($stage, () => is_valid = true);

            if (is_valid === false) {
                return;
            }
        }

        $stage.addClass("fade-out");
    });

    $segments.on("transitionend", function (e) {
        // cast to integer and add one.
        const id = 1 + +$(this).data("stage");

        if ($(this).hasClass("fade-out")) {
            $(this).removeClass("fade-out show");

            setTimeout(function () {
                $segments.filter("[data-stage='" + id + "']").addClass("show");
                if (typeof callbacks.change[id] === "function") {
                    callbacks.change[id]();
                }
            }, 300);
        }
    });

    return {
        display: function (idx) {
            $segments.filter("[data-stage='" + (idx - 1) + "']").addClass("fade-out");
            return this;
        },

        change: function (idx, func) {
            callbacks.change[idx] = func;
            return this;
        },

        validate: function (idx, func) {
            callbacks.validate[idx] = func;
            return this;
        },
    };
};

var validateInputPartial = (function () {
    // when the body is ready, add the "animationend" functionality.
    $(function () {
        // when any of the `.shake` elements stop animating, remove them so that
        // the animation can be re-triggered again.
        $("body").on("animationend", ".shake", function () {
            $(this).removeClass("shake");
        });
    });

    return function ($parent, callback) {
        var is_invalid = false;

        // find all the forms of inputs that we can validate.
        $parent.find("input, select, textarea").each(function () {
            // check the validity of each with the HTML5 validation API.
            var is_valid = this.checkValidity();
            var $this = $(this);
            var $parent = $this.closest(".input-box");
            var $label = $parent.find(".text");

            // if there is no supplied error and the input IS required, supply
            // a sample error.
            if (!$label.data("error") && $this.attr("required") === "required") {
                $label.attr("data-error", "(This field is required.)");
            }

            is_invalid = !is_valid || is_invalid;

            // add red/shake animation if invalid.
            if (!is_valid) {
                $this.addClass("shake")
                    .closest(".input-box").addClass("error");
                return;
            }

            $this.closest(".input-box").removeClass("error");
        });

        if (!is_invalid) {
            callback();
        }
    };
}());

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

    $('#password_reset').validate({
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

    $(".register-button.next").click(function (e) {
        e.preventDefault();
    });

    Segments($("#registration"))
        .validate(0, validateInputPartial);
});
