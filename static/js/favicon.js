var favicon = (function () {

var exports = {};

var favicon_selector = 'link[rel="shortcut icon"]';

// We need to reset the favicon after changing the
// window.location.hash or Firefox will drop the favicon.  See
// https://bugzilla.mozilla.org/show_bug.cgi?id=519028
exports.reset = function () {
    $(favicon_selector).detach().appendTo('head');
};

exports.set = function (url) {
    if (/webkit/i.test(navigator.userAgent)) {
        // Works in Chrome 22 at least.
        // Doesn't work in Firefox 10.
        $(favicon_selector).attr('href', url);
    } else {
        // Delete and re-create the node.
        // May cause excessive work by the browser
        // in re-rendering the page (see #882).
        $(favicon_selector).remove();
        $('head').append($('<link>')
            .attr('rel', 'shortcut icon')
            .attr('href', url));
    }
};


return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = favicon;
}
