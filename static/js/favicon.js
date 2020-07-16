exports.set = function (url) {
    $("#favicon").attr("href", url || "/static/images/favicon.svg?v=5");
    $("#favicon-16x16").attr("href", url || "/static/images/favicon-16x16.png?v=5");
};

window.favicon = exports;
