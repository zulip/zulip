/// <reference types="webpack-dev-server" />

import path from "path";

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
        cacheDirectory: path.resolve(__dirname, "var/webpack-cache"),
    },
};

export default (_env: unknown, argv: {mode?: string}): webpack.Configuration[] => {
    const production: boolean = argv.mode === "production";

    const config: webpack.Configuration = {
        name: "frontend",
        mode: production ? "production" : "development",
        context: __dirname,
        entry: production
            ? assets
            : Object.fromEntries(
                  Object.entries(assets).map(([name, paths]) => [
                      name,
                      [...paths, "./static/js/debug"],
                  ]),
              ),
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
                        path.resolve(__dirname, "static/shared/js"),
                        path.resolve(__dirname, "static/js"),
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
                    exclude: path.resolve(__dirname, "static/styles"),
                    use: [
                        MiniCssExtractPlugin.loader,
                        cacheLoader,
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
                    include: path.resolve(__dirname, "static/styles"),
                    use: [
                        MiniCssExtractPlugin.loader,
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
                    test: /\.(eot|jpg|svg|ttf|otf|png|woff2?)$/,
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
            path: path.resolve(__dirname, "static/webpack-bundles"),
            filename: production ? "[name].[contenthash].js" : "[name].js",
            chunkFilename: production ? "[contenthash].js" : "[id].js",
        },
        resolve: {
            extensions: [".ts", ".js"],
        },
        // We prefer cheap-module-source-map over any eval-* options
        // because stacktrace-gps doesn't currently support extracting
        // the source snippets with the eval-* options.
        devtool: production ? "source-map" : "cheap-module-source-map",
        optimization: {
            minimizer: [
                // Based on a comment in NMFR/optimize-css-assets-webpack-plugin#10.
                // Can be simplified when NMFR/optimize-css-assets-webpack-plugin#87
                // is fixed.
                new OptimizeCssAssetsPlugin({
                    cssProcessor: {
                        async process(css, options: any) {
                            const filename = path.basename(options.to);
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
            new webpack.ProgressPlugin({
                handler(percentage) {
                    if (percentage === 1) {
                        console.log(
                            "\u001B[34mi ｢wdm｣\u001B[0m:",
                            "Webpack compilation successful.",
                        );
                    }
                },
            }),
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
        devServer: {
            clientLogLevel: "error",
            headers: {
                "Access-Control-Allow-Origin": "*",
            },
            publicPath: "/webpack/",
            stats: "errors-only",
            noInfo: true,
        },
    };

    const serverConfig: webpack.Configuration = {
        name: "server",
        mode: production ? "production" : "development",
        target: "node",
        context: __dirname,
        entry: {
            "katex-cli": "shebang-loader!katex/cli",
        },
        output: {
            path: path.resolve(__dirname, "static/webpack-bundles"),
            filename: "[name].js",
        },
    };

    return [config, serverConfig];
};
