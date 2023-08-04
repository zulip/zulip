"use strict";

module.exports = (api) => ({
    plugins: [
        [
            "formatjs",
            {
                additionalFunctionNames: ["$t", "$t_html"],
                overrideIdFn: (_id, defaultMessage) => defaultMessage,
            },
        ],
        ...(api.env("test")
            ? [
                  ...(process.env.USING_INSTRUMENTED_CODE ? [["istanbul", {exclude: []}]] : []),
                  "rewire-ts",
                  ["@babel/plugin-transform-modules-commonjs", {lazy: () => true}],
              ]
            : []),
    ],
    presets: [
        [
            "@babel/preset-env",
            {
                corejs: "3.31",
                shippedProposals: true,
                useBuiltIns: "usage",
            },
        ],
        "@babel/typescript",
    ],
    sourceType: "unambiguous",
});
