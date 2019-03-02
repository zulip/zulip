$(function () {
    // This code will be executed when the user visits /login and
    // dev_login.html is rendered.
    if ($("[data-page-id='dev-login']").length > 0) {
        if (window.location.hash.substring(0, 1) === "#") {
            /* We append the location.hash to the formaction so that URL can be
            preserved after user is logged in. See this:
            https://stackoverflow.com/questions/5283395/url-hash-is-persisting-between-redirects */
            $("input[name='direct_email']").each(function () {
                var new_formaction = $(this).attr('formaction') + '/' + window.location.hash;
                $(this).attr('formaction', new_formaction);
            });
        }
    }
});
