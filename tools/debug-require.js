"use strict";

/* global __webpack_require__ */

var webpackModules;

function debugRequire(request) {
    if (!Object.prototype.hasOwnProperty.call(debugRequire.ids, request)) {
        throw new Error("Cannot find module '" + request + "'");
    }
    var moduleId = debugRequire.ids[request];
    if (!Object.prototype.hasOwnProperty.call(webpackModules, moduleId)) {
        throw new Error("Module '" + request + "' has not been loaded yet");
    }
    return __webpack_require__(moduleId);
}

debugRequire.initialize = function (ids, modules) {
    debugRequire.ids = ids;
    webpackModules = modules;
};

module.exports = debugRequire;
