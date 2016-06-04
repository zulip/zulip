// Miscellaneous early setup.

var csrf_token;
$(function () {
    // Display loading indicator.  This disappears after the first
    // get_events completes.
    if (page_params.have_initial_messages && !page_params.needs_tutorial) {
        loading.make_indicator($('#page_loading_indicator'), {text: 'Loading...'});
    } else if (!page_params.needs_tutorial) {
        $('#first_run_message').show();
    }

    // This requires that we used Django's {% csrf_token %} somewhere on the page.
    csrf_token = $('input[name="csrfmiddlewaretoken"]').attr('value');

    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
            if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
                // Only send the token to relative URLs i.e. locally.
                xhr.setRequestHeader("X-CSRFToken", csrf_token);
            }
        }
    });

    // For some reason, jQuery wants this to be attached to an element.
    $('body').ajaxError(function (event, xhr) {
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
    }

});


