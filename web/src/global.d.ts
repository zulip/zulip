// These declarations tell the TypeScript compiler about the existence
// of the global variables for our untyped JavaScript modules.  Please
// remove each declaration when the corresponding module is migrated
// to TS.

declare let zulip_test: any; // eslint-disable-line @typescript-eslint/no-explicit-any

interface JQuery {
    /**
     * Bootstrap carousel planned for removal soon, this type definition should be
     * removed correpondingly. More information here https://github.com/zulip/zulip/pull/24301
     */
    carousel: (
        option?:
            | "cycle"
            | "next"
            | "pause"
            | "prev"
            | number
            | {
                  interval: number | false;
              }
            | {
                  pause: "hover" | boolean;
              },
    ) => void;
    expectOne(): JQuery;
    tab(action?: string): this; // From web/third/bootstrap
}

declare const ZULIP_VERSION: string;
