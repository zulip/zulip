"use strict";

module.exports = {
    bracketSpacing: false,
    trailingComma: "all",
    overrides: [
        {
            files: ["tsconfig.json"],
            options: {
                parser: "json5",
                quoteProps: "preserve",
            },
        },
    ],
};
