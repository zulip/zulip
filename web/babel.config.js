// @ts-check

/** @type {Parameters<typeof import("babel-plugin-formatjs").default>[1]} */
const formatJsOptions = {
    additionalFunctionNames: ["$t", "$t_html"],
    overrideIdFn: (_id, defaultMessage) => defaultMessage ?? "",
};

/** @type {import("@babel/preset-env").Options} */
const presetEnvOptions = {
    corejs: "3.48",
    shippedProposals: true,
    useBuiltIns: "usage",
};

/** @type {import("@babel/core").TransformOptions} */
const config = {
    plugins: [["formatjs", formatJsOptions]],
    presets: [["@babel/preset-env", presetEnvOptions], "@babel/typescript"],
};
export default config;
