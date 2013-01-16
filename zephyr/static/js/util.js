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

exports.make_loading_indicator = function (container, text) {
    container.empty();
    var spinner_elem = $('<div class="loading_indicator_spinner"></div>');
    container.append(spinner_elem);
    var text_width = 0;

    if (text !== '' && text !== undefined) {
        var text_elem = $('<span class="loading_indicator_text"></span>');
        text_elem.text(text);
        container.append(text_elem);
        // See note, below
        text_width = 20 + text_elem.width();
    }

    // These width calculations are tied to the spinner width and
    // margins defined via CSS
    container.css({width: 38 + text_width,
                   height: 38,
                   display: 'block'});

    var spinner = new Spinner({
        lines: 8,
        length: 0,
        width: 9,
        radius: 9,
        speed: 1.25,
        shadow: false
    }).spin(spinner_elem[0]);
    container.data("spinner_obj", spinner);
};

exports.destroy_loading_indicator = function (container) {
    var spinner = container.data("spinner_obj");
    if (spinner !== undefined) {
        spinner.stop();
    }
    container.removeData("spinner_obj");
    container.empty();
    container.css({width: 0, height: 0, display: 'none'});
};

return exports;
}());
