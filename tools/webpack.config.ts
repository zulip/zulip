import { resolve } from 'path';
import * as BundleTracker from 'webpack-bundle-tracker';
import * as webpack from 'webpack';

const assets = require('./webpack.assets.json');

// Only use the Webpack 2.0 Rule definitions.
interface Config extends webpack.Configuration {
  module: {
    rules: webpack.NewUseRule[]
  }
}

export default (env?: string) : Config => {
    const production: boolean = env === "production";
    let config: Config = {
        context: resolve(__dirname, "../"),
        entry: assets,
        module: {
            rules: [
                // Run the typescript compilier on .ts files before webpack
                {
                    test: /\.tsx?$/,
                    use: 'ts-loader',
                },
                // This loads and transforms sourcemap files from other compiliers.
                // The typescript comilier will generate a sourcemap and
                // source-map-loader will output the correct sourcemap from that.
                {
                    enforce: 'pre',
                    test: /\.js$/,
                    use: "source-map-loader",
                },
                {
                    enforce: 'pre',
                    test: /\.tsx?$/,
                    use: "source-map-loader",
                },
                // Uses script-loader on minified files so we don't change global variables in them.
                // Also has the effect of making processing these files fast
                // Currently the source maps don't work with these so use unminified files
                // if debugging is required.
                {
                    test: /(min|zxcvbn)\.js/,
                    use: [ 'script-loader' ],
                },
                // Expose Global variables to webpack
                // Use the unminified versions of jquery and underscore so that
                // Good error messages show up in production and development in the source maps
                {
                    test: require.resolve('../static/node_modules/jquery/dist/jquery.js'),
                    use: [
                        {loader: 'expose-loader', options: '$'},
                        {loader: 'expose-loader', options: 'jQuery'},
                    ],
                },
                {
                    test: require.resolve('../node_modules/underscore/underscore.js'),
                    use: [
                        {loader: 'expose-loader', options: '_'},
                    ],
                },
                {
                    test: require.resolve('../static/js/debug.js'),
                    use: [
                        {loader: 'expose-loader', options: 'debug'},
                    ],
                },
                {
                    test: require.resolve('../static/js/blueslip.js'),
                    use: [
                        {loader: 'expose-loader', options: 'blueslip'},
                    ],
                },
                {
                    test: require.resolve('../static/js/common.js'),
                    use: [
                        {loader: 'expose-loader', options: 'common'},
                    ],
                },
            ],
        },
        output: {
            path: resolve(__dirname, '../static/webpack-bundles'),
            filename: production ? '[name]-[hash].js' : '[name].js',
        },
        resolve: {
            extensions: [".tsx", ".ts", ".js", ".json"],
        },
        devtool: production ? 'source-map' : 'eval',
    };
    if (production) {
        config.plugins = [
            new BundleTracker({filename: 'webpack-stats-production.json'}),
        ];
    } else {
        // Built webpack dev asset reloader
        config.entry['common'].unshift('webpack/hot/dev-server');
        // Use 0.0.0.0 so that we can set a port but still use the host
        // the browser is connected to.
        config.entry['common'].unshift('webpack-dev-server/client?http://0.0.0.0:9994');

        // Out JS debugging tools
        config.entry['common'].push('./static/js/debug.js');

        config.output.publicPath = '/webpack/';
        config.plugins = [
            new BundleTracker({filename: 'var/webpack-stats-dev.json'}),
            // Hot Reload of code in development
            new webpack.HotModuleReplacementPlugin(),
            // Better logging from console for hot reload
            new webpack.NamedModulesPlugin(),
            // script-loader should load sourceURL in dev
            new webpack.LoaderOptionsPlugin({debug: true}),
        ];

        config.devServer = {
            clientLogLevel: "warning",
            hot: true,
            inline: false,
            stats: "errors-only",
            watchOptions: {
                aggregateTimeout: 300,
                poll: 1000,
            },
        };
    }
    return config;
};
