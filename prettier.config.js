module.exports = {
    bracketSpacing: false,
    tabWidth: 4,
    trailingComma: "all",
    overrides: [
        {
            files: ["frontend_tests/casper_tests/*.js", "frontend_tests/casper_lib/*.js"],
            options: {
                trailingComma: "es5",
            },
        },
        {
            files: ["**.yml", "**.yaml"],
            options: {
                tabWidth: 2,
            },
        },
    ],
};
