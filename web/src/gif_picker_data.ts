import * as channel from "./channel.ts";
import type {GiphyPayload} from "./giphy.ts";
import type {TenorPayload} from "./tenor.ts";

export async function fetch_gifs(data: TenorPayload | GiphyPayload, url: string): Promise<unknown> {
    return new Promise((resolve) => {
        channel.get({
            url,
            data,
            success: resolve,
        });
    });
}
