import {gtag, install} from "ga-gtag";
import type {ConfigParams} from "ga-gtag";

import {page_params} from "../base_page_params.ts";

export let config: (info: ConfigParams) => void;

if (page_params.google_analytics_id !== undefined) {
    install(page_params.google_analytics_id);
    config = (info) => {
        gtag("config", page_params.google_analytics_id!, info);
    };
} else {
    config = () => {
        // No Google Analytics tracking configured.
    };
}

export function trackMacArchDetection(
    architecture: string,
    confidence: 'high' | 'low' | 'unknown',
    method: string,
): void {
    try {
        if (page_params.google_analytics_id !== undefined) {
            gtag('event', 'mac_arch_detected', {
                architecture,
                confidence,
                detection_method: method,
                timestamp: new Date().toISOString(),
            });
        }
    } catch {
        // swallow analytics errors
    }
}

export function trackMacDownloadClicked(architecture: string): void {
    try {
        if (page_params.google_analytics_id !== undefined) {
            gtag('event', 'mac_download_clicked', {
                architecture,
                timestamp: new Date().toISOString(),
            });
        }
    } catch {
        // swallow analytics errors
    }
}
