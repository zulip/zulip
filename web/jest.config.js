"use strict";

const escapeRegExp = require("lodash/escapeRegExp");

module.exports = {
    cacheDirectory: "<rootDir>/../var/jest_rs",
    collectCoverageFrom: [
        "<rootDir>/**/*.{js,ts,hbs}",
        "!**/*.d.ts",
        "!<rootDir>/../static/webpack-bundles/**",
    ],
    coverageDirectory: "<rootDir>/../var/node-coverage",
    globalSetup: "<rootDir>/tests/lib/global_setup.js",
    setupFilesAfterEnv: ["<rootDir>/tests/lib/index.js"],
    testEnvironment: "node",
    testMatch: ["<rootDir>/tests/*.test.{js,ts}"],
    transform: {
        ["^" + escapeRegExp(__dirname) + "(/src|/shared/src)/.*\\.(js|ts)$"]: "babel-jest",
        "\\.hbs$": "<rootDir>/tests/lib/handlebars.js",
    },
};
