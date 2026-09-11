"use strict";

module.exports = {
    files: ["./*.svg"],
    fontName: "zulip-icons",
    classPrefix: "zulip-icon-",
    baseSelector: ".zulip-icon",
    cssTemplate: "./template.hbs",
    ligature: false,
    // Keep woff2 as the preferred format, but emit woff as a fallback for
    // browsers/WebViews that fail to load the custom icon font reliably.
    types: ["woff2", "woff"],
};
