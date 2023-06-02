/**
 * npm module name:- "ga-gtag"
 * version:-  "^1.0.1"
 */
/**
 * This can be improved using zulip specific information
 * on fields that can be passed with this object into the
 * `install` function.
 */
declare type AdditionalConfigInfo = Record<string, unknown>;

// Type reference: https://github.com/idmadj/ga-gtag/blob/6917019745209525c641ac1698d76ff9ebf9a80a/src/index.js
export declare const install: (
    trackingId: string,
    additionalConfigInfo?: AdditionalConfigInfo,
) => void;

export declare const gtag: Gtag.Gtag;
export default gtag;
