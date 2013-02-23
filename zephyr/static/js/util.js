var util = (function () {

var exports = {};

// From MDN: https://developer.mozilla.org/en-US/docs/JavaScript/Reference/Global_Objects/Math/random
exports.random_int = function random_int(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
};

var favicon_selector = 'link[rel="shortcut icon"]';

// We need to reset the favicon after changing the
// window.location.hash or Firefox will drop the favicon.  See
// https://bugzilla.mozilla.org/show_bug.cgi?id=519028
exports.reset_favicon = function () {
    $(favicon_selector).detach().appendTo('head');
};

exports.set_favicon = function (url) {
    // I'm not sure whether setting the href attr on the existing
    // node would be sufficient.  Notificon recreates the node.
    $(favicon_selector).remove();
    $('head').append($('<link>')
        .attr('rel',  'shortcut icon')
        .attr('href', url));
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
    //
    // TODO: We set white-space to 'nowrap' because under some
    // unknown circumstances (it happens on Keegan's laptop) the text
    // width calculation, above, returns a result that's a few pixels
    // too small.  The container's div will be slightly too small,
    // but that's probably OK for our purposes.
    container.css({width: 38 + text_width,
                   height: 38,
                   display: 'block',
                   'white-space': 'nowrap'});

    var spinner = new Spinner({
        lines: 8,
        length: 0,
        width: 9,
        radius: 9,
        speed: 1.25,
        shadow: false,
        zIndex: 1000
    }).spin(spinner_elem[0]);
    container.data("spinner_obj", spinner);

    // Make the spinner appear in the center of its enclosing
    // element.  spinner.el is a 0x0 div.  The parts of the spinner
    // are arranged so that they're centered on the upper-left corner
    // of spinner.el.  So, by setting spinner.el's position to
    // relative and top/left to 50%, the center of the spinner will
    // be located at the center of spinner_elem.
    $(spinner.el).css({left: '50%', top: '50%'});
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

exports.show_first_run_message = function () {
    $('#first_run_message').show();
};

exports.destroy_first_run_message = function () {
    // A no-op if the element no longer exists
    $('#first_run_message').remove();
};

exports.show_empty_narrow_message = function () {
    $('#empty_narrow_message').show();
};

exports.hide_empty_narrow_message = function () {
    $('#empty_narrow_message').hide();
};

// Takes a one-argument function.  Returns a variant of that
// function which caches result values.
//
// Since this uses a JavaScript object as the cache structure,
// arguments with the same string representation will be
// considered equal.
exports.memoize = function (fun) {
    var table = {};

    return function (arg) {
        // See #351; we should have a generic associative data
        // structure instead.
        if (! Object.prototype.hasOwnProperty.call(table, arg)) {
            table[arg] = fun(arg);
        }
        return table[arg];
    };
};

// Like C++'s std::lower_bound.  Returns the first index at which
// `value` could be inserted without changing the ordering.  Assumes
// the array is sorted.
//
// `first` and `last` are indices and `less` is an optionally-specified
// function that returns true if
//   array[i] < value
// for some i and false otherwise.
//
// Usage: lower_bound(array, value, [less])
//        lower_bound(array, first, last, value, [less])
exports.lower_bound = function (array, arg1, arg2, arg3, arg4) {
    var first, last, value, less;
    if (arg3 === undefined) {
        first = 0;
        last = array.length;
        value = arg1;
        less = arg2;
    } else {
        first = arg1;
        last = arg2;
        value = arg3;
        less = arg4;
    }

    if (less === undefined) {
        less = function (a, b) { return a < b; };
    }

    var len = last - first;
    var middle;
    var step;
    var lower = 0;
    while (len > 0) {
        step = Math.floor(len / 2);
        middle = first + step;
        if (less(array[middle], value)) {
            first = middle;
            first++;
            len = len - step - 1;
        }
        else {
            len = step;
        }
    }
    return first;
};

return exports;
}());
