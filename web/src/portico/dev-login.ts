import $ from "jquery";

$(() => {
    // This code will be executed when the user visits /login and
    // dev_login.html is rendered.
    if ($("[data-page-id='dev-login']").length > 0 && window.location.hash.startsWith("#")) {
        /* We append the location.hash to the input field with name next so that URL can be
            preserved after user is logged in. See this:
            https://stackoverflow.com/questions/5283395/url-hash-is-persisting-between-redirects */
        $("input[name='next']").each(function () {
            const new_value = $(this).attr("value")! + window.location.hash;
            $(this).attr("value", new_value);
        });
    }
});
