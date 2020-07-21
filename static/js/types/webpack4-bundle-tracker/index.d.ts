import {Plugin} from "webpack";

declare namespace BundleTracker {
    interface Options {
        path?: string;
        filename?: string;
        publicPath?: string;
        logTime?: boolean;
    }
}

// eslint-disable-next-line no-redeclare
declare class BundleTracker extends Plugin {
    constructor(options?: BundleTracker.Options);
}

export = BundleTracker;
