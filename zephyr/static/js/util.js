var util = (function () {

var exports = {};

// From MDN: https://developer.mozilla.org/en-US/docs/JavaScript/Reference/Global_Objects/Math/random
exports.random_int = function random_int(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
};

// We need to reset the favicon after changing the
// window.location.hash or Firefox will drop the favicon.  See
// https://bugzilla.mozilla.org/show_bug.cgi?id=519028
exports.reset_favicon = function () {
    $('link[rel="shortcut icon"]').detach().appendTo('head');
};

exports.make_spinner = function (container, text) {
    // assumes that container is a table
    var row = $('<tr>');
    var spinner_elem = $('<td class="loading_spinner"></td>');
    var text_elem = $('<td></td>');
    text_elem.text(text);

    row.append(spinner_elem, text_elem);
    container.append(row);

    var spinner = new Spinner({
        lines: 8,
        length: 0,
        width: 9,
        radius: 9,
        speed: 1.25,
        shadow: false
    }).spin(spinner_elem[0]);
    return spinner;
};

return exports;
}());
