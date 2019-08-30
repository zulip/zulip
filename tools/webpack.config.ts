import { basename, resolve } from 'path';
import * as BundleTracker from 'webpack-bundle-tracker';
import * as webpack from 'webpack';
// The devServer member of webpack.Configuration is managed by the
// webpack-dev-server package. We are only importing the type here.
import * as _webpackDevServer from 'webpack-dev-server';
import { getExposeLoaders, cacheLoader } from './webpack-helpers';
import * as MiniCssExtractPlugin from 'mini-css-extract-plugin';
import * as OptimizeCssAssetsPlugin from 'optimize-css-assets-webpack-plugin';
import * as CleanCss from 'clean-css';
import * as TerserPlugin from 'terser-webpack-plugin';

const assets = require('./webpack.assets.json');

export default (env?: string): webpack.Configuration[] => {
    const production: boolean = env === "production";
    const publicPath = production ? '/static/webpack-bundles/' : '/webpack/';
    const config: webpack.Configuration = {
        name: "frontend",
        mode: production ? "production" : "development",
        context: resolve(__dirname, "../"),
        entry: assets,
        module: {
            rules: [
                // Generate webfont
                {
                    test: /\.font\.js$/,
                    use: [
                        MiniCssExtractPlugin.loader,
                        'css-loader',
                        {
                            loader: 'webfonts-loader',
                            options: {
                                fileName: production ? 'files/[fontname].[chunkhash].[ext]' : 'files/[fontname].[ext]',
                                publicPath,
                            },
                        },
                    ],
                },
                // Transpile .js and .ts files with Babel
                {
                    test: /\.(js|ts)$/,
                    include: resolve(__dirname, '../static/js'),
                    loader: 'babel-loader',
                },
                // Uses script-loader on minified files so we don't change global variables in them.
                // Also has the effect of making processing these files fast
                // Currently the source maps don't work with these so use unminified files
                // if debugging is required.
                {
                    // We dont want to match admin.js
                    test: /(\.min|min\.|zxcvbn)\.js/,
                    use: [cacheLoader, 'script-loader'],
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
                            loader: 'css-loader',
                            options: {
                                sourceMap: true,
                            },
                        },
                    ],
                },
                // scss loader
                {
                    test: /\.scss$/,
                    include: resolve(__dirname, '../static/styles'),
                    use: [
                        {
                            loader: MiniCssExtractPlugin.loader,
                            options: {
                                hmr: !production,
                            },
                        },
                        cacheLoader,
                        {
                            loader: 'css-loader',
                            options: {
                                importLoaders: 1,
                                sourceMap: true,
                            },
                        },
                        {
                            loader: 'postcss-loader',
                            options: {
                                sourceMap: true,
                            },
                        },
                    ],
                },
                {
                    test: /\.hbs$/,
                    loader: 'handlebars-loader',
                    options: {
                        // Tell webpack not to explicitly require these.
                        knownHelpers: ['if', 'unless', 'each', 'with',
                            // The ones below are defined in static/js/templates.js
                            'plural', 'eq', 'and', 'or', 'not',
                            't', 'tr'],
                        preventIndent: true,
                    },
                },
                // load fonts and files
                {
                    test: /\.(woff(2)?|ttf|eot|svg|otf|png)$/,
                    use: [{
                        loader: 'file-loader',
                        options: {
                            name: production ? '[name].[hash].[ext]' : '[name].[ext]',
                            outputPath: 'files/',
                        },
                    }],
                },
            ],
        },
        output: {
            path: resolve(__dirname, '../static/webpack-bundles'),
            publicPath,
            filename: production ? '[name].[chunkhash].js' : '[name].js',
        },
        resolve: {
            extensions: [".ts", ".js"],
        },
        // We prefer cheap-module-source-map over any eval-** options
        // because the eval-options currently don't support being
        // source mapped in error stack traces
        // We prefer it over eval since eval has trouble setting
        // breakpoints in chrome.
        devtool: production ? 'source-map' : 'cheap-module-source-map',
        optimization: {
            minimizer: [
                // Based on a comment in NMFR/optimize-css-assets-webpack-plugin#10.
                // Can be simplified when NMFR/optimize-css-assets-webpack-plugin#87
                // is fixed.
                new OptimizeCssAssetsPlugin({
                    cssProcessor: {
                        process: async (css, options) => {
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
        },
    };

    // Expose Global variables for third party libraries to webpack modules
    // Use the unminified versions of jquery and underscore so that
    // Good error messages show up in production and development in the source maps
    var exposeOptions = [
        { path: "blueimp-md5/js/md5.js" },
        { path: "clipboard/dist/clipboard.js", name: "ClipboardJS" },
        { path: "xdate/src/xdate.js", name: "XDate" },
        { path: "simplebar/dist/simplebar.js"},
        { path: "../static/third/marked/lib/marked.js" },
        { path: "../static/generated/emoji/emoji_codes.js" },
        { path: "../static/generated/pygments_data.js" },
        { path: "../static/js/debug.js" },
        { path: "../static/js/blueslip.js" },
        { path: "../static/js/common.js" },
        { path: "jquery/dist/jquery.js", name: ['$', 'jQuery'] },
        { path: "underscore/underscore.js", name: '_' },
        { path: "handlebars/dist/cjs/handlebars.runtime.js", name: 'Handlebars' },
        { path: "to-markdown/dist/to-markdown.js", name: 'toMarkdown' },
        { path: "sortablejs/Sortable.js"},
        { path: "winchan/winchan.js", name: 'WinChan'},
    ];
    config.module.rules.unshift(...getExposeLoaders(exposeOptions));

    if (production) {
        config.plugins = [
            new BundleTracker({filename: 'webpack-stats-production.json'}),
            // Extract CSS from files
            new MiniCssExtractPlugin({
                filename: (data) => {
                    // This is a special case in order to produce
                    // a static CSS file to be consumed by
                    // static/html/5xx.html
                    if (data.chunk.name === 'error-styles') {
                        return 'error-styles.css';
                    }
                    return '[name].[contenthash].css';
                },
                chunkFilename: "[chunkhash].css",
            }),
        ];
    } else {
        // Out JS debugging tools
        config.entry['common'].push('./static/js/debug.js');  // eslint-disable-line dot-notation

        config.plugins = [
            new BundleTracker({filename: 'var/webpack-stats-dev.json'}),
            // Better logging from console for hot reload
            new webpack.NamedModulesPlugin(),
            // script-loader should load sourceURL in dev
            new webpack.LoaderOptionsPlugin({debug: true}),
            // Extract CSS from files
            new MiniCssExtractPlugin({
                filename: "[name].css",
                chunkFilename: "[chunkhash].css",
            }),
        ];
        config.devServer = {
            clientLogLevel: "error",
            stats: "errors-only",
        };
    }

    const serverConfig: webpack.Configuration = {
        mode: production ? "production" : "development",
        target: "node",
        context: resolve(__dirname, "../"),
        entry: {
            "katex-cli": "shebang-loader!katex/cli",
        },
        output: {
            path: resolve(__dirname, "../static/webpack-bundles"),
            filename: "[name].js",
        },
    };

    return [config, serverConfig];
};
