/*jslint browser: true, devel: true, sloppy: true,
    plusplus: true, white: true */
/*global $: false */

function autofocus(selector) {
    $(function () {
        $(selector)[0].focus();
    });
}
