/**
 * This is not complete type definitions for the "Winchan" module, but it's enough
 * for our purpose.
 */
declare module "winchan" {
    type WinchanOpts = {
        url: string;
        relay_url: string;
        params: Record<string, unknown>;
    };

    export function open(
        winchanOpts: WinchanOpts,
        cb: (err: string, response: unknown) => void,
    ): void;
}
