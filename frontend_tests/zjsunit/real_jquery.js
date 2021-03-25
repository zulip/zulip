"use strict";

const jquery = require("jquery");

// so the tests can mock jQuery
delete require.cache[require.resolve("jquery")];

module.exports = jquery;
