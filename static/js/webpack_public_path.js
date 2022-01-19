/* eslint-env commonjs */
// eslint-disable-next-line no-unused-vars
/* global __webpack_public_path__:writable */

"use strict";

const {page_params} = require("./page_params");

// Webpack exposes this global for dynamic configuration of publicPath.
// https://webpack.js.org/guides/public-path/#on-the-fly
__webpack_public_path__ = page_params.webpack_public_path;
