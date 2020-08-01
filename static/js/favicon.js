"use strict";

exports.set = function (url) {
    $("#favicon").attr("href", url);
};

window.favicon = exports;
