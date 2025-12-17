import * as channel from "./channel.ts";
import type {TenorPayload} from "./tenor.ts";

export async function fetch_tenor_gifs(data: TenorPayload, url: string): Promise<unknown> {
    return new Promise((resolve) => {
        channel.get({
            url,
            data,
            success: resolve,
        });
    });
}
