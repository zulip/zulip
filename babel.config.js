module.exports = {
    presets: [
        [
            "@babel/preset-env",
            {
                corejs: 3,
                loose: true, // Loose mode for…of loops are 5× faster in Firefox
                useBuiltIns: "usage",
            },
        ],
        "@babel/typescript",
    ],
    plugins: [
        "@babel/proposal-class-properties",
        ["@babel/plugin-proposal-unicode-property-regex", {useUnicodeFlag: false}],
    ],
    sourceType: "unambiguous",
};
