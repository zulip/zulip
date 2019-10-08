import { resolve } from 'path';
import * as BundleTracker from 'webpack-bundle-tracker';
import * as webpack from 'webpack';
import { getExposeLoaders, getImportLoaders } from './webpack-helpers';
const MiniCssExtractPlugin = require("mini-css-extract-plugin");

const assets = require('./webpack.assets.json');

// Adds on css-hot-loader in dev mode
function getHotCSS(bundle:any[], isProd:boolean) {
    if(isProd) {
        return bundle;
    }
    return [
        'css-hot-loader',
    ].concat(bundle);
}

export default (env?: string) : webpack.Configuration => {
    const production: boolean = env === "production";
    let config: webpack.Configuration = {
        mode: production ? "production" : "development",
        context: resolve(__dirname, "../"),
        entry: assets,
        module: {
            rules: [
                // Run the typescript compilier on .ts files before webpack
                {
                    test: /\.tsx?$/,
                    loader: 'ts-loader',
                    options: {
                        configFile: require.resolve('../static/ts/tsconfig.json')
                    }
                },
                // Uses script-loader on minified files so we don't change global variables in them.
                // Also has the effect of making processing these files fast
                // Currently the source maps don't work with these so use unminified files
                // if debugging is required.
                {
                    // We dont want to match admin.js
                    test: /(\.min|min\.|zxcvbn)\.js/,
                    use: [ 'script-loader' ],
                },
                // regular css files
                {
                    test: /\.css$/,
                    use: getHotCSS([
                        MiniCssExtractPlugin.loader,
                        {
                            loader: 'css-loader',
                            options: {
                                sourceMap: true
                            },
                        },
                    ], production)
                },
                // sass / scss loader
                {
                    test: /\.(sass|scss)$/,
                    use: getHotCSS([
                        MiniCssExtractPlugin.loader,
                        {
                            loader: 'css-loader',
                            options: {
                                sourceMap: true
                            }
                        },
                        {
                            loader: 'sass-loader',
                            options: {
                                sourceMap: true
                            }
                        }
                    ], production),
                },
                // load fonts and files
                {
                    test: /\.(woff(2)?|ttf|eot|svg|otf|png)(\?v=\d+\.\d+\.\d+)?$/,
                    use: [{
                        loader: 'file-loader',
                        options: {
                            name: '[name].[ext]',
                            outputPath: 'files/'
                        }
                    }]
                }
            ],
        },
        output: {
            path: resolve(__dirname, '../static/webpack-bundles'),
            filename: production ? '[name].[chunkhash].js' : '[name].js',
        },
        resolve: {
            modules: [
                resolve(__dirname, "../static"),
                resolve(__dirname, "../node_modules"),
                resolve(__dirname, "../"),
            ],
            extensions: [".tsx", ".ts", ".js", ".json", ".scss", ".css"],
        },
        // We prefer cheap-module-source-map over any eval-** options
        // because the eval-options currently don't support being
        // source mapped in error stack traces
        // We prefer it over eval since eval has trouble setting
        // breakpoints in chrome.
        devtool: production ? 'source-map' : 'cheap-module-source-map',
    };

    // Add variables within modules
    // Because of code corecing the value of window within the libraries
    var importsOptions = [
        {
            path: "../static/third/spectrum/spectrum.js",
            args: "this=>window"
        }
    ];
    config.module.rules.push(...getImportLoaders(importsOptions));

    // Expose Global variables for third party libraries to webpack modules
    // Use the unminified versions of jquery and underscore so that
    // Good error messages show up in production and development in the source maps
    var exposeOptions = [
        { path: "../node_modules/blueimp-md5/js/md5.js" },
        { path: "../node_modules/clipboard/dist/clipboard.js", name: "ClipboardJS" },
        { path: "../node_modules/xdate/src/xdate.js", name: "XDate" },
        { path: "../node_modules/perfect-scrollbar/dist/perfect-scrollbar.js", name: "PerfectScrollbar" },
        { path: "../node_modules/simplebar/dist/simplebar.js"},
        { path: "../static/third/marked/lib/marked.js" },
        { path: "../static/generated/emoji/emoji_codes.js" },
        { path: "../static/generated/pygments_data.js" },
        { path: "../static/js/debug.js" },
        { path: "../static/js/blueslip.js" },
        { path: "../static/js/common.js" },
        { path: "../node_modules/jquery/dist/jquery.js", name: ['$', 'jQuery'] },
        { path: "../node_modules/underscore/underscore.js", name: '_' },
        { path: "../node_modules/handlebars/dist/handlebars.runtime.js", name: 'Handlebars' },
        { path: "../node_modules/to-markdown/dist/to-markdown.js", name: 'toMarkdown' },
        { path: "../node_modules/sortablejs/Sortable.js"},
        { path: "../node_modules/winchan/winchan.js", name: 'WinChan'}
    ];
    config.module.rules.push(...getExposeLoaders(exposeOptions));

    if (production) {
        config.plugins = [
            new BundleTracker({filename: 'webpack-stats-production.json'}),
            // Extract CSS from files
            new MiniCssExtractPlugin({
                filename: (data) => {
                    // This is a special case in order to produce
                    // a static CSS file to be consumed by
                    // static/html/5xx.html
                    if(data.chunk.name === 'error-styles') {
                        return 'error-styles.css';
                    }
                    return '[name].[contenthash].css';
                },
                chunkFilename: "[chunkhash].css"
            })
        ];
    } else {
        // Out JS debugging tools
        config.entry['common'].push('./static/js/debug.js');

        config.output.publicPath = '/webpack/';
        config.plugins = [
            new BundleTracker({filename: 'var/webpack-stats-dev.json'}),
            // Better logging from console for hot reload
            new webpack.NamedModulesPlugin(),
            // script-loader should load sourceURL in dev
            new webpack.LoaderOptionsPlugin({debug: true}),
            // Extract CSS from files
            new MiniCssExtractPlugin({
                filename: "[name].css",
                chunkFilename: "[chunkhash].css"
            }),
        ];
        config.devServer = {
            clientLogLevel: "error",
            stats: "errors-only",
            watchOptions: {
                poll: 100
            }
        };
    }
    return config;
};
