// Miscellaneous early setup.

var csrf_token;
$(function () {
    if (util.is_mobile()) {
        // if the client is mobile, disable websockets for message sending
        // (it doesn't work on iOS for some reason).
        page_params.use_websockets = false;
        // Also disable the tutorial; it's ugly on mobile.
        page_params.needs_tutorial = false;
    }

    page_params.page_load_time = new Date().getTime();

    // Display loading indicator.  This disappears after the first
    // get_events completes.
    if (page_params.have_initial_messages && !page_params.needs_tutorial) {
        loading.make_indicator($('#page_loading_indicator'), {text: 'Loading...', abs_positioned: true});
    } else if (!page_params.needs_tutorial) {
        $('#first_run_message').show();
    }

    // This requires that we used Django's {% csrf_token %} somewhere on the page.
    csrf_token = $('input[name="csrfmiddlewaretoken"]').attr('value');


    // This is an issue fix where in jQuery v3 the result of outerHeight on a node
    // that doesn’t exist is now “undefined” rather than “null”, which means it
    // will no longer cast to a Number but rather NaN. For this, we create the
    // `safeOuterHeight` and `safeOuterWidth` functions to safely return a result
    // (or 0).
    $.fn.safeOuterHeight = function () {
        return $(this).outerHeight.apply(this, arguments) || 0;
    };

    $.fn.safeOuterWidth = function () {
        return $(this).outerWidth.apply(this, arguments) || 0;
    };

    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
            if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
                // Only send the token to relative URLs i.e. locally.
                xhr.setRequestHeader("X-CSRFToken", csrf_token);
            }
        },
    });

    // For some reason, jQuery wants this to be attached to an element.
    $(document).ajaxError(function (event, xhr) {
        if (xhr.status === 401) {
            // We got logged out somehow, perhaps from another window or a session timeout.
            // We could display an error message, but jumping right to the login page seems
            // smoother and conveys the same information.
            window.location.replace(page_params.login_page);
        }
    });

    if (typeof $ !== 'undefined') {
        $.fn.expectOne = function () {
            if (blueslip && this.length !== 1) {
                blueslip.error("Expected one element in jQuery set, " + this.length + " found");
            }
            return this;
        };

        $.fn.within = function (sel) {
            return ($(this).is(sel) || $(this).closest(sel).length);
        };
    }

});
