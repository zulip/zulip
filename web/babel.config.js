// @ts-check

import path from "node:path";

import _ from "lodash";

/** @type {Parameters<typeof import("babel-plugin-formatjs").default>[1]} */
const formatJsOptions = {
    additionalFunctionNames: ["$t", "$t_html"],
    overrideIdFn: (_id, defaultMessage) => defaultMessage ?? "",
};

/** @type {import("@babel/preset-env").Options} */
const presetEnvOptions = {
    shippedProposals: true,
};

/** @type {import("@babel/core").PluginItem} */
const istanbulPlugin = ["istanbul", {exclude: []}];

/** @type {import("@babel/core").InputOptions} */
const config = {
    only: [new RegExp("^" + _.escapeRegExp(path.resolve(import.meta.dirname, "src") + path.sep))],
    plugins: [
        ["formatjs", formatJsOptions],
        ["polyfill-corejs3", {method: "usage-global", version: "3.49"}],
    ],
    presets: [["@babel/preset-env", presetEnvOptions], "@babel/typescript"],
    env: {
        test: {
            plugins: [
                ...(process.env["USING_INSTRUMENTED_CODE"] ? [istanbulPlugin] : []),
                ["@babel/plugin-transform-modules-commonjs", {lazy: () => true}],
            ],
        },
    },
};
export default config;
