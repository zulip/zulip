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
    ],
    sourceType: "unambiguous",
};
