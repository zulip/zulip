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

export declare const install: (
    trackingId: string,
    additionalConfigInfo?: AdditionalConfigInfo,
) => void;
/**
 * Improvements can be made using zulip specific information
 * on values that can be passed as arguments in this function.
 */
export declare const gtag: (...args: unknown[]) => void;
export default gtag;
