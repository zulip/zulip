export default {
    bracketSpacing: false,
    trailingComma: "all",
    plugins: ["prettier-plugin-astro"],
    overrides: [
        {
            files: ["tsconfig.json"],
            options: {
                parser: "json5",
                quoteProps: "preserve",
            },
        },
        {
            files: ["*.md"],
            options: {
                embeddedLanguageFormatting: "off",
            },
        },
        {
            files: "*.astro",
            options: {
                parser: "astro",
            },
        },
    ],
};
