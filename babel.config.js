"use strict";

module.exports = {
    presets: [
        [
            "@babel/preset-env",
            {
                corejs: "3.6",
                loose: true, // Loose mode for…of loops are 5× faster in Firefox
                shippedProposals: true,
                useBuiltIns: "usage",
            },
        ],
        "@babel/typescript",
    ],
    sourceType: "unambiguous",
};
