import { resolve } from 'path';
import * as BundleTracker from 'webpack-bundle-tracker';
import * as webpack from 'webpack';
const MiniCssExtractPlugin = require("mini-css-extract-plugin");

const assets = require('./webpack.assets.json');

// Adds on css-hot-loader in dev mode
function getHotCSS(bundle: any[], isProd: boolean) {
    if (isProd) {
        return bundle;
    }
    return [
        'css-hot-loader',
    ].concat(bundle);
}
export default (env?: string): webpack.Configuration => {
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
                    test: /(min|zxcvbn)\.js/,
                    use: ['script-loader'],
                },
                // Expose Global variables to webpack
                // Use the unminified versions of jquery and underscore so that
                // Good error messages show up in production and development in the source maps
                {
                    test: require.resolve('../static/node_modules/jquery/dist/jquery.js'),
                    use: [
                        { loader: 'expose-loader', options: '$' },
                        { loader: 'expose-loader', options: 'jQuery' },
                    ],
                },
                {
                    test: require.resolve('../node_modules/underscore/underscore.js'),
                    use: [
                        { loader: 'expose-loader', options: '_' },
                    ],
                },
                {
                    test: require.resolve('../static/js/debug.js'),
                    use: [
                        { loader: 'expose-loader', options: 'debug' },
                    ],
                },
                {
                    test: require.resolve('../static/js/blueslip.js'),
                    use: [
                        { loader: 'expose-loader', options: 'blueslip' },
                    ],
                },
                {
                    test: require.resolve('../static/js/common.js'),
                    use: [
                        { loader: 'expose-loader', options: 'common' },
                    ],
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
                            }
                        },
                    ], production),
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
            filename: production ? '[name]-[hash].js' : '[name].js',
        },
        resolve: {
            extensions: [".tsx", ".ts", ".js", ".json", ".scss", ".css"],
        },
        // We prefer cheap-module-eval-source-map over eval because
        // currently eval has trouble setting breakpoints per line
        // in Google Chrome. There's almost no difference
        // between the compilation time for the two and could be
        // re-evaluated as the size of files grows
        devtool: production ? 'source-map' : 'cheap-module-eval-source-map',
    };
    if (production) {
        config.plugins = [
            new BundleTracker({ filename: 'webpack-stats-production.json' }),
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
                chunkFilename: "[id].css"
            })
        ];
    } else {
        // Out JS debugging tools
        config.entry['common'].push('./static/js/debug.js');

        config.output.publicPath = '/webpack/';
        config.plugins = [
            new BundleTracker({ filename: 'var/webpack-stats-dev.json' }),
            // Better logging from console for hot reload
            new webpack.NamedModulesPlugin(),
            // script-loader should load sourceURL in dev
            new webpack.LoaderOptionsPlugin({ debug: true }),
            // Extract CSS from files
            new MiniCssExtractPlugin({
                filename: "[name].css",
                chunkFilename: "[id].css"
            }),
            // We use SourceMapDevToolPlugin in order to enable SourceMaps
            // in combination with mini-css-extract-plugin and
            // the devtool setting of cheap-module-eval-source-map.
            // Without this plugin source maps won't work with that combo.
            // See https://github.com/webpack-contrib/mini-css-extract-plugin/issues/29
            new webpack.SourceMapDevToolPlugin({
                filename: "[file].map"
            })
        ];

        config.devServer = {
            clientLogLevel: "error",
            stats: "errors-only",
            watchOptions:
                {
                    poll: 100
                }
        };
    }
    return config;
};
