// @ts-check

import path from "node:path";

import postcssExtendRule from "postcss-extend-rule";
import postcssImport from "postcss-import";
import postcssPrefixWrap from "postcss-prefixwrap";
import postcssPresetEnv from "postcss-preset-env";
import postcssSimpleVars from "postcss-simple-vars";

import {container_breakpoints, media_breakpoints} from "./src/css_variables.ts";

/**
 * @param {object} ctx
 * @returns {import("postcss-load-config").Config}
 * @satisfies {import("postcss-load-config").ConfigFn & import("postcss-loader/dist/config").PostCSSLoaderOptions}
 */
const config = (ctx) => ({
    plugins: [
        "file" in ctx &&
            (typeof ctx.file === "string"
                ? path.basename(ctx.file)
                : typeof ctx.file === "object" && ctx.file !== null && "basename" in ctx.file
                  ? ctx.file.basename
                  : undefined) === "dark_theme.css" &&
            // Add postcss-import plugin with postcss-prefixwrap to handle
            // the flatpickr dark theme. We do this because flatpickr themes
            // are not scoped. See https://github.com/flatpickr/flatpickr/issues/2168.
            postcssImport({
                plugins: [postcssPrefixWrap("%dark-theme")],
            }),
        postcssExtendRule,
        postcssSimpleVars({variables: {...container_breakpoints, ...media_breakpoints}}),
        postcssPresetEnv({
            features: {
                "is-pseudo-class": true, // Needed for postcss-extend-rule
                "nesting-rules": true,
            },
        }),
    ],
});
export default config;
