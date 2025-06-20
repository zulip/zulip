export default {
    plugins: [
        [
            "formatjs",
            {
                additionalFunctionNames: ["$t", "$t_html"],
                idInterpolationPattern: "[sha512:contenthash:base64:6]",
            },
        ],
    ],
    presets: [
        [
            "@babel/preset-env",
            {
                corejs: "3.42",
                shippedProposals: true,
                useBuiltIns: "usage",
            },
        ],
        "@babel/typescript",
    ],
};
