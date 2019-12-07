module.exports = {
    presets: [
        [
            "@babel/preset-env",
            {
                corejs: 3,
                useBuiltIns: "usage",
            },
        ],
        "@babel/typescript",
    ],
    plugins: [
        "@babel/proposal-class-properties",
        ["@babel/plugin-proposal-unicode-property-regex", { useUnicodeFlag: false }],
    ],
    sourceType: "unambiguous",
};
