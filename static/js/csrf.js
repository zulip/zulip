import $ from "jquery";

export let csrf_token;

$(() => {
    // This requires that we used Jinja2's {% csrf_input %} somewhere on the page.
    const csrf_input = $('input[name="csrfmiddlewaretoken"]');
    csrf_token = csrf_input.attr("value");
    if (csrf_token === undefined) {
        return;
    }

    $.ajaxSetup({
        beforeSend(xhr, settings) {
            if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
                // Only send the token to relative URLs i.e. locally.
                xhr.setRequestHeader("X-CSRFToken", csrf_token);
            }
        },
    });
});
