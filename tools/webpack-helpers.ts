import {resolve} from "path";

import {RuleSetUseItem} from "webpack";

export const cacheLoader: RuleSetUseItem = {
    loader: "cache-loader",
    options: {
        cacheDirectory: resolve(__dirname, "../var/webpack-cache"),
    },
};
