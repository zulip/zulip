/* global __webpack_require__ */

function debugRequire(request) {
    return __webpack_require__(debugRequire.ids[request]);
}

debugRequire.initialize = function (ids) {
    debugRequire.ids = ids;
};

module.exports = debugRequire;
