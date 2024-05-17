"use strict";

module.exports = {
    plugins: [
        [
            "formatjs",
            {
                additionalFunctionNames: ["$t", "$t_html"],
                overrideIdFn: (_id, defaultMessage) => defaultMessage,
            },
        ],
    ],
    presets: [
        [
            "@babel/preset-env",
            {
                corejs: "3.37",
                include: ["transform-optional-chaining"],
                shippedProposals: true,
                useBuiltIns: "usage",
            },
        ],
        "@babel/typescript",
    ],
    sourceType: "unambiguous",
};
