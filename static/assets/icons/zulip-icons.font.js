/* eslint-env commonjs */

"use strict";

module.exports = {
    files: [
        "./*.svg", // For web-only icons.
        "../../shared/icons/*.svg", // For icons to be shared with the mobile app.

        "../../shared/icons/feather/*.svg",
    ],
    fontName: "zulip-icons",
    classPrefix: "zulip-icon-",
    baseSelector: ".zulip-icon",
    cssTemplate: "./template.hbs",
    ligature: false,
};
