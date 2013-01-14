var timerender = (function () {

var exports = {};

// Given an XDate object 'time', return a DOM node that initially
// displays the human-formatted time, and is updated automatically as
// necessary (e.g. changing "Mon 11:21" to "Jan 14 11:21" after a week
// or so).

// (But for now it just returns a static node.)
exports.render_time = function(time) {
    // Wrap the text in a span because (oddly) a text node has no outerHTML attribute.
    return $("<span />").text(time.toString("MMM dd") + "\xa0\xa0" + time.toString("HH:mm"));
};

return exports;
}());
