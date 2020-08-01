"use strict";

/* global __webpack_public_path__:writable */

const t1 = performance.now();
window.page_params = $("#page-params").remove().data("params");
const t2 = performance.now();
window.page_params_parse_time = t2 - t1;
if (!window.page_params) {
    throw new Error("Missing page-params");
}

// Webpack exposes this global for dynamic configuration of publicPath.
// https://webpack.js.org/guides/public-path/#on-the-fly
__webpack_public_path__ = window.page_params.webpack_public_path;
