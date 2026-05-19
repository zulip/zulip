import * as z from "zod/mini";

export let get_retry_backoff_seconds = (
    xhr: JQuery.jqXHR<unknown> | undefined,
    attempts: number,
    faster_backoff = false,
): number => {
    // We need to respect the server's rate-limiting headers, but beyond
    // that, we also want to avoid contributing to a thundering herd if
    // the server is giving us 500/502 responses.
    //
    // We do the maximum of the retry-after header and an exponential
    // backoff.
    let backoff_scale: number;
    if (faster_backoff) {
        // Starts at 1-2s and ends at 16-32s after enough failures.
        backoff_scale = Math.min(2 ** attempts, 32);
    } else {
        // Starts at 1-2s and ends at 45-90s after enough failures.
        backoff_scale = Math.min(2 ** ((attempts + 1) / 2), 90);
    }
    // Add a bit jitter to backoff scale.
    const backoff_delay_secs = ((1 + Math.random()) / 2) * backoff_scale;
    let rate_limit_delay_secs = 0;
    const rate_limited_error_schema = z.object({
        "retry-after": z.number(),
        code: z.literal("RATE_LIMIT_HIT"),
    });
    const parsed = rate_limited_error_schema.safeParse(xhr?.responseJSON);
    if (xhr?.status === 429 && parsed?.success && parsed?.data) {
        // Add a bit of jitter to the required delay suggested by the
        // server, because we may be racing with other copies of the web
        // app.
        rate_limit_delay_secs = parsed.data["retry-after"] + Math.random() * 0.5;
    }
    return Math.max(backoff_delay_secs, rate_limit_delay_secs);
};

export function rewire_get_retry_backoff_seconds(value: typeof get_retry_backoff_seconds): void {
    get_retry_backoff_seconds = value;
}
