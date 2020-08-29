/// <reference types="webpack-dev-server" />

import {basename, resolve} from "path";

import CleanCss from "clean-css";
import HtmlWebpackPlugin from "html-webpack-plugin";
import MiniCssExtractPlugin from "mini-css-extract-plugin";
import OptimizeCssAssetsPlugin from "optimize-css-assets-webpack-plugin";
import TerserPlugin from "terser-webpack-plugin";
import webpack from "webpack";
import BundleTracker from "webpack4-bundle-tracker";

import DebugRequirePlugin from "./tools/debug-require-webpack-plugin";
import assets from "./tools/webpack.assets.json";

const cacheLoader: webpack.RuleSetUseItem = {
    loader: "cache-loader",
    options: {
        cacheDirectory: resolve(__dirname, "var/webpack-cache"),
    },
};

export default (env?: string): webpack.Configuration[] => {
    const production: boolean = env === "production";
    const config: webpack.Configuration = {
        name: "frontend",
        mode: production ? "production" : "development",
        context: __dirname,
        entry: assets,
        module: {
            rules: [
                {
                    test: require.resolve("./tools/debug-require"),
                    loader: "expose-loader",
                    options: {exposes: "require"},
                },
                {
                    test: require.resolve("jquery"),
                    loader: "expose-loader",
                    options: {exposes: ["$", "jQuery"]},
                },
                // Generate webfont
                {
                    test: /\.font\.js$/,
                    use: [
                        MiniCssExtractPlugin.loader,
                        {
                            loader: "css-loader",
                            options: {
                                url: false, // webfonts-loader generates public relative URLs
                            },
                        },
                        {
                            loader: "webfonts-loader",
                            options: {
                                fileName: production
                                    ? "files/[fontname].[chunkhash].[ext]"
                                    : "files/[fontname].[ext]",
                                publicPath: "",
                            },
                        },
                    ],
                },
                // Transpile .js and .ts files with Babel
                {
                    test: /\.(js|ts)$/,
                    include: [
                        resolve(__dirname, "static/shared/js"),
                        resolve(__dirname, "static/js"),
                    ],
                    use: [cacheLoader, "babel-loader"],
                },
                // Uses script-loader on minified files so we don't change global variables in them.
                // Also has the effect of making processing these files fast
                // Currently the source maps don't work with these so use unminified files
                // if debugging is required.
                {
                    // We dont want to match admin.js
                    test: /(\.min|min\.|zxcvbn)\.js/,
                    use: [cacheLoader, "script-loader"],
                },
                // regular css files
                {
                    test: /\.css$/,
                    use: [
                        {
                            loader: MiniCssExtractPlugin.loader,
                            options: {
                                hmr: !production,
                            },
                        },
                        cacheLoader,
                        {
                            loader: "css-loader",
                            options: {
                                sourceMap: true,
                            },
                        },
                    ],
                },
                // scss loader
                {
                    test: /\.scss$/,
                    include: resolve(__dirname, "static/styles"),
                    use: [
                        {
                            loader: MiniCssExtractPlugin.loader,
                            options: {
                                hmr: !production,
                            },
                        },
                        cacheLoader,
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
                    use: [
                        cacheLoader,
                        {
                            loader: "handlebars-loader",
                            options: {
                                // Tell webpack not to explicitly require these.
                                knownHelpers: [
                                    "if",
                                    "unless",
                                    "each",
                                    "with",
                                    // The ones below are defined in static/js/templates.js
                                    "plural",
                                    "eq",
                                    "and",
                                    "or",
                                    "not",
                                    "t",
                                    "tr",
                                    "rendered_markdown",
                                ],
                                preventIndent: true,
                            },
                        },
                    ],
                },
                // load fonts and files
                {
                    test: /\.(woff(2)?|ttf|eot|svg|otf|png)$/,
                    use: [
                        {
                            loader: "file-loader",
                            options: {
                                name: production ? "[name].[hash].[ext]" : "[path][name].[ext]",
                                outputPath: "files/",
                            },
                        },
                    ],
                },
            ],
        },
        output: {
            path: resolve(__dirname, "static/webpack-bundles"),
            filename: production ? "[name].[contenthash].js" : "[name].js",
            chunkFilename: production ? "[contenthash].js" : "[id].js",
        },
        resolve: {
            extensions: [".ts", ".js"],
        },
        // We prefer cheap-module-source-map over any eval-** options
        // because the eval-options currently don't support being
        // source mapped in error stack traces
        // We prefer it over eval since eval has trouble setting
        // breakpoints in chrome.
        devtool: production ? "source-map" : "cheap-module-source-map",
        optimization: {
            minimizer: [
                // Based on a comment in NMFR/optimize-css-assets-webpack-plugin#10.
                // Can be simplified when NMFR/optimize-css-assets-webpack-plugin#87
                // is fixed.
                new OptimizeCssAssetsPlugin({
                    cssProcessor: {
                        async process(css, options: any) {
                            const filename = basename(options.to);
                            const result = await new CleanCss(options).minify({
                                [filename]: {
                                    styles: css,
                                    sourceMap: options.map.prev,
                                },
                            });
                            for (const warning of result.warnings) {
                                console.warn(warning);
                            }
                            return {
                                css: result.styles + `\n/*# sourceMappingURL=${filename}.map */`,
                                map: result.sourceMap,
                            };
                        },
                    },
                    cssProcessorOptions: {
                        map: {},
                        returnPromise: true,
                        sourceMap: true,
                        sourceMapInlineSources: true,
                    },
                }),
                new TerserPlugin({
                    cache: true,
                    parallel: true,
                    sourceMap: true,
                }),
            ],
            splitChunks: {
                chunks: "all",
                // webpack/examples/many-pages suggests 20 requests for HTTP/2
                maxAsyncRequests: 20,
                maxInitialRequests: 20,
            },
        },
        plugins: [
            new DebugRequirePlugin(),
            new BundleTracker({
                filename: production
                    ? "webpack-stats-production.json"
                    : "var/webpack-stats-dev.json",
            }),
            ...(production
                ? []
                : [
                      // Better logging from console for hot reload
                      new webpack.NamedModulesPlugin(),
                      // script-loader should load sourceURL in dev
                      new webpack.LoaderOptionsPlugin({debug: true}),
                  ]),
            // Extract CSS from files
            new MiniCssExtractPlugin({
                filename: production ? "[name].[contenthash].css" : "[name].css",
                chunkFilename: production ? "[contenthash].css" : "[id].css",
            }),
            new HtmlWebpackPlugin({
                filename: "5xx.html",
                template: "static/html/5xx.html",
                chunks: ["error-styles"],
            }),
        ],
    };

    if (!production) {
        // Out JS debugging tools
        for (const paths of Object.values(assets)) {
            paths.push("./static/js/debug");
        }
        config.devServer = {
            clientLogLevel: "error",
            headers: {
                "Access-Control-Allow-Origin": "*",
            },
            publicPath: "/webpack/",
            stats: "errors-only",
        };
    }

    const serverConfig: webpack.Configuration = {
        mode: production ? "production" : "development",
        target: "node",
        context: __dirname,
        entry: {
            "katex-cli": "shebang-loader!katex/cli",
        },
        output: {
            path: resolve(__dirname, "static/webpack-bundles"),
            filename: "[name].js",
        },
    };

    return [config, serverConfig];
};
