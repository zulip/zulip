import {basename, resolve} from "path";

import {RuleSetRule, RuleSetUseItem} from "webpack";

export const cacheLoader: RuleSetUseItem = {
    loader: "cache-loader",
    options: {
        cacheDirectory: resolve(__dirname, "../var/webpack-cache"),
    },
};

/* Return expose-loader format to the config
    For example
    [
        // Exposes 'my_module' as the name
        {path: './folder/my_module.js'},

        // Exposes 'my_custom_name'
        {path: './folder/my_module.js', name: 'my_custom_name'},

        // Exposes 'name1' and 'name2'
        {path: './folder/my_module.js', name: ['name1', 'name2']}
    ]
*/
interface ExportLoaderOptions {
    path: string;
    name?: string | string[];
}

export function getExposeLoaders(optionsArr: ExportLoaderOptions[]): RuleSetRule[] {
    return optionsArr.map(({path, name}) => ({
        test: require.resolve(path),
        use: [
            cacheLoader,
            {
                loader: "expose-loader",
                options: {
                    // If no name is provided, infer it
                    exposes: name ?? basename(path, ".js"),
                },
            },
        ],
    }));
}
