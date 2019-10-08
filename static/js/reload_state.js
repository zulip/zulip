var reload_state = (function () {

var exports = {};

/*
    We want his module to load pretty early in the process
    of starting the app, so that people.js can load early.
    All the heavy lifting for reload logic happens in
    reload.js, which has lots of UI dependencies.  If we
    didn't split out this module, our whole dependency tree
    would be kind of upside down.
*/

var reload_in_progress = false;
var reload_pending = false;

exports.is_pending = function () {
    return reload_pending;
};

exports.is_in_progress = function () {
    return reload_in_progress;
};

exports.set_state_to_pending = function () {
    // Why do we never set this back to false?
    // Because the reload is gonna happen next. :)
    // I was briefly confused by this, hence the comment.
    reload_pending = true;
};

exports.set_state_to_in_progress = function () {
    reload_in_progress = true;
};


return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = reload_state;
}
window.reload_state = reload_state;
