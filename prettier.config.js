module.exports = {
    bracketSpacing: false,
    trailingComma: "all",
    overrides: [
        {
            files: ["frontend_tests/casper_tests/*.js", "frontend_tests/casper_lib/*.js"],
            options: {
                trailingComma: "es5",
            },
        },
        {
            files: ["tsconfig.json"],
            options: {
                parser: "json5",
                quoteProps: "preserve",
            },
        },
    ],
};
