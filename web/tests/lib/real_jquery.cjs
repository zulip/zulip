"use strict";

const jquery = require("jquery");

// so the tests can mock jQuery
// eslint-disable-next-line @typescript-eslint/no-dynamic-delete
delete require.cache[require.resolve("jquery")];

module.exports = jquery;
