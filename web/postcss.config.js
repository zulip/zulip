import path from "node:path";

import postcssExtendRule from "postcss-extend-rule";
import postcssImport from "postcss-import";
import postcssPrefixWrap from "postcss-prefixwrap";
import postcssPresetEnv from "postcss-preset-env";
import postcssSimpleVars from "postcss-simple-vars";

import {media_breakpoints} from "./src/css_variables.ts";

const config = ({file}) => ({
    plugins: [
        (file.basename ?? path.basename(file)) === "dark_theme.css" &&
            // Add postcss-import plugin with postcss-prefixwrap to handle
            // the flatpickr dark theme. We do this because flatpickr themes
            // are not scoped. See https://github.com/flatpickr/flatpickr/issues/2168.
            postcssImport({
                plugins: [postcssPrefixWrap("%dark-theme")],
            }),
        postcssExtendRule,
        postcssSimpleVars({variables: media_breakpoints}),
        postcssPresetEnv({
            features: {
                "nesting-rules": true,
            },
        }),
    ],
});
export default config;
