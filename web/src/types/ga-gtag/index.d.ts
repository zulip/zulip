/// <reference types="gtag.js" />

/* global Gtag */

/**
 * npm module name: "ga-gtag"
 * version:  "1.2.0"
 */

export type ConfigParams = Gtag.GtagCommands["config"][1];

// Type reference: https://github.com/idmadj/ga-gtag/blob/eb7a97d153cbfedbc81344fd59123f737b8a5cb8/src/index.js
export declare const install: (trackingId: string, additionalConfigInfo?: ConfigParams) => void;

export declare const gtag: Gtag.Gtag;
