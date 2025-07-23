// @ts-check

/** @type {import("babel-plugin-formatjs/types").Options} */
const formatJsOptions = {
    additionalFunctionNames: ["$t", "$t_html"],
    idInterpolationPattern: "[sha512:contenthash:base64:6]",
};

/** @type {import("@babel/preset-env").Options} */
const presetEnvOptions = {
    corejs: "3.48",
    shippedProposals: true,
    useBuiltIns: "usage",
};

/** @type {import("@babel/core").TransformOptions} */
export default {
    plugins: [["formatjs", formatJsOptions]],
    presets: [["@babel/preset-env", presetEnvOptions], "@babel/typescript"],
};
