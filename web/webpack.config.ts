/// <reference types="webpack-dev-server" />

import path from "node:path";
import * as url from "node:url";

import type {ZopfliOptions} from "@gfx/zopfli";
import {gzip} from "@gfx/zopfli";
import CompressionPlugin from "compression-webpack-plugin";
import CssMinimizerPlugin from "css-minimizer-webpack-plugin";
import HtmlWebpackPlugin from "html-webpack-plugin";
import MiniCssExtractPlugin from "mini-css-extract-plugin";
import webpack from "webpack";
import BundleTracker from "webpack-bundle-tracker";

import DebugRequirePlugin from "./debug-require-webpack-plugin.ts";
import assets from "./webpack.assets.json" with {type: "json"};
import dev_assets from "./webpack.dev-assets.json" with {type: "json"};

const config = (
    env: {
        minimize?: true;
        puppeteer_tests?: true;
        ZULIP_VERSION?: string;
        custom_5xx_file?: string;
    } = {},
    argv: {mode?: string},
): webpack.Configuration[] => {
    const production: boolean = argv.mode === "production";

    const baseConfig: webpack.Configuration = {
        mode: production ? "production" : "development",
        context: import.meta.dirname,
        cache: {
            type: "filesystem",
            buildDependencies: {
                config: [import.meta.filename],
            },
        },
    };

    const plugins: webpack.WebpackPluginInstance[] = [
        new webpack.DefinePlugin({
            DEVELOPMENT: JSON.stringify(!production),
            ZULIP_VERSION: JSON.stringify(env.ZULIP_VERSION ?? "development"),
        }),
        new DebugRequirePlugin(),
        new BundleTracker({
            path: path.join(import.meta.dirname, production ? ".." : "../var"),
            filename: production ? "webpack-stats-production.json" : "webpack-stats-dev.json",
        }),
        // Extract CSS from files
        new MiniCssExtractPlugin({
            filename: production ? "[name].[contenthash].css" : "[name].css",
            chunkFilename: production ? "[contenthash].css" : "[id].css",
        }),
        new HtmlWebpackPlugin({
            filename: "5xx.html",
            template: env.custom_5xx_file ? "html/" + env.custom_5xx_file : "html/5xx.html",
            chunks: ["error-styles"],
            publicPath: production ? "/static/webpack-bundles/" : "/webpack/",
        }),
    ];
    if (production && !env.puppeteer_tests) {
        plugins.push(
            new CompressionPlugin<ZopfliOptions>({
                // Use zopfli to write pre-compressed versions of text files
                test: /\.(js|css|html)$/,
                algorithm: gzip,
            }),
        );
    }

    const frontendConfig: webpack.Configuration = {
        ...baseConfig,
        name: "frontend",
        entry: production
            ? assets
            : Object.fromEntries(
                  Object.entries({...assets, ...dev_assets}).map(([name, paths]) => [
                      name,
                      [...paths, "./src/debug.ts"],
                  ]),
              ),
        module: {
            rules: [
                {
                    test: path.resolve(import.meta.dirname, "src/zulip_test.ts"),
                    loader: "expose-loader",
                    options: {exposes: "zulip_test"},
                },
                {
                    test: path.resolve(import.meta.dirname, "debug-require.cjs"),
                    loader: "expose-loader",
                    options: {exposes: "require"},
                },
                {
                    test: url.fileURLToPath(import.meta.resolve("jquery")),
                    loader: "expose-loader",
                    options: {exposes: ["$", "jQuery"]},
                },
                // Generate webfont
                {
                    test: /\.font\.cjs$/,
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
                    type: "javascript/auto",
                },
                // Transpile .js and .ts files with Babel
                {
                    test: /\.[cm]?[jt]s$/,
                    include: [
                        path.resolve(import.meta.dirname, "shared/src"),
                        path.resolve(import.meta.dirname, "src"),
                    ],
                    loader: "babel-loader",
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
                // load fonts and files
                {
                    test: /\.(eot|jpg|svg|ttf|otf|png|webp|woff2?)$/,
                    type: "asset/resource",
                },
            ],
        },
        output: {
            path: path.resolve(import.meta.dirname, "../static/webpack-bundles"),
            publicPath: "auto",
            filename: production ? "[name].[contenthash].js" : "[name].js",
            assetModuleFilename: production
                ? "files/[name].[hash][ext][query]"
                : // Avoid directory traversal bug that upstream won't fix
                  // (https://github.com/webpack/webpack/issues/11937)
                  (pathData) => "files" + path.join("/", pathData.filename!),
            chunkFilename: production ? "[contenthash].js" : "[id].js",
            crossOriginLoading: "anonymous",
        },
        // We prefer cheap-module-source-map over any eval-* options
        // because stacktrace-gps doesn't currently support extracting
        // the source snippets with the eval-* options.
        devtool: production ? "source-map" : "cheap-module-source-map",
        optimization: {
            minimize: env.minimize ?? production,
            minimizer: [
                new CssMinimizerPlugin({
                    minify: CssMinimizerPlugin.cleanCssMinify,
                }),
                "...",
            ],
            splitChunks: {
                chunks: "all",
                // webpack/examples/many-pages suggests 20 requests for HTTP/2
                maxAsyncRequests: 20,
                maxInitialRequests: 20,
            },
        },
        plugins,
        devServer: {
            client: {
                overlay: {
                    runtimeErrors: false,
                },
            },
            devMiddleware: {
                publicPath: "/webpack/",
                stats: {
                    // We want just errors and a clear, brief notice
                    // whenever webpack compilation has finished.
                    preset: "minimal",
                    assets: false,
                    modules: false,
                },
            },
            headers: {
                "Access-Control-Allow-Origin": "*",
                "Timing-Allow-Origin": "*",
            },
            setupMiddlewares: (middlewares) =>
                middlewares.filter((middleware) => middleware.name !== "cross-origin-header-check"),
        },
        infrastructureLogging: {
            level: "warn",
        },
        watchOptions: {
            ignored: [
                "**/node_modules/**",
                // Prevent Emacs file locks from crashing webpack-dev-server
                // https://github.com/webpack/webpack-dev-server/issues/2821
                "**/.#*",
            ],
        },
    };

    const serverConfig: webpack.Configuration = {
        ...baseConfig,
        name: "server",
        target: "node",
        entry: {
            katex_server: "babel-loader!./server/katex_server.ts",
            "katex-cli": "shebang-loader!katex/cli",
        },
        output: {
            path: path.resolve(import.meta.dirname, "../static/webpack-bundles"),
        },
    };

    return [frontendConfig, serverConfig];
};
export default config;
