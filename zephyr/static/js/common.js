/*jslint browser: true, devel: true, sloppy: true,
    plusplus: true, white: true, undef: true */
/*global $: false */

function autofocus(selector) {
    $(function () {
        $(selector)[0].focus();
    });
}
