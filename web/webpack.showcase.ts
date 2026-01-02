import path from "node:path";

import MiniCssExtractPlugin from "mini-css-extract-plugin";
import type webpack from "webpack";

const config = (): webpack.Configuration => {
    const showcase_config: webpack.Configuration = {
        mode: "development",
        devtool: "source-map",
        name: "showcase-config",
        context: import.meta.dirname,
        entry: "./src/bundles/showcase.ts",
        plugins: [
            new MiniCssExtractPlugin({
                filename: "[name].css",
            }),
        ],
        module: {
            rules: [
                // Transpile .js and .ts files with Babel
                {
                    test: /\.[cm]?[jt]s$/,
                    include: [path.resolve(import.meta.dirname, "src")],
                    loader: "babel-loader",
                    options: {
                        presets: [
                            ["@babel/preset-typescript", {allowDeclareFields: true}],
                            [
                                "@babel/preset-env",
                                {
                                    targets: {esmodules: true}, // modern JS
                                    modules: false,
                                    loose: true,
                                },
                            ],
                        ],
                        comments: true, // keeps comments in the output
                        retainLines: true, // try to keep line numbers
                        compact: false, // disables compact/minified output
                    },
                },
                // regular css files
                {
                    test: /\.css$/,
                    exclude: path.resolve(import.meta.dirname, "styles"),
                    use: [
                        MiniCssExtractPlugin.loader,
                        {
                            loader: "css-loader",
                            options: {
                                sourceMap: true,
                            },
                        },
                    ],
                },
                // PostCSS loader
                {
                    test: /\.css$/,
                    include: path.resolve(import.meta.dirname, "styles"),
                    use: [
                        MiniCssExtractPlugin.loader,
                        {
                            loader: "css-loader",
                            options: {
                                importLoaders: 1,
                                sourceMap: true,
                            },
                        },
                        {
                            loader: "postcss-loader",
                            options: {
                                sourceMap: true,
                            },
                        },
                    ],
                },
                {
                    test: /\.hbs$/,
                    loader: "handlebars-loader",
                    options: {
                        ignoreHelpers: true,
                        // Tell webpack not to explicitly require these.
                        knownHelpers: [
                            // The ones below are defined in web/src/templates.ts
                            "eq",
                            "and",
                            "or",
                            "not",
                            "t",
                            "tr",
                            "rendered_markdown",
                            "numberFormat",
                            "tooltip_hotkey_hints",
                            "popover_hotkey_hints",
                        ],
                        precompileOptions: {
                            knownHelpersOnly: true,
                            strict: true,
                            explicitPartialContext: true,
                        },
                        preventIndent: true,
                        // This replaces relative image resources with
                        // a computed require() path to them, so their
                        // webpack-hashed URLs are used.
                        inlineRequires: /^(\.\.\/)+(images|static)\//,
                    },
                },
            ],
        },
        output: {
            path: path.resolve(import.meta.dirname, "showcase-build"),
            filename: "showcase.js",
        },
    };
    return showcase_config;
};
export default config;
