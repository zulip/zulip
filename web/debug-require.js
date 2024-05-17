"use strict";

/* global __webpack_require__ */

function debugRequire(request) {
    if (!Object.prototype.hasOwnProperty.call(debugRequire.ids, request)) {
        throw new Error("Cannot find module '" + request + "'");
    }
    var moduleId = debugRequire.ids[request];
    if (!Object.prototype.hasOwnProperty.call(__webpack_require__.m, moduleId)) {
        throw new Error("Module '" + request + "' has not been loaded yet");
    }
    return __webpack_require__(moduleId);
}

debugRequire.r = __webpack_require__;
debugRequire.ids = __webpack_require__.debugRequireIds;

module.exports = debugRequire;
