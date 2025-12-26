import assert from "minimalistic-assert";
import * as z from "zod/mini";

import {
    type GifInfoUrl,
    GifNetwork,
    type GifProvider,
    type RenderGifsCallback,
} from "./abstract_gif_network.ts";
import * as channel from "./channel.ts";
import {get_rating} from "./gif_state.ts";
import {realm} from "./state_data.ts";
import {user_settings} from "./user_settings.ts";

const BASE_URL = "https://api.giphy.com/v1/gifs";
// Source: https://developers.giphy.com/docs/api/endpoint
export type GiphyPayload = {
    api_key: string;
    limit: number;
    offset: number;
    rating: string;
    // Lets us reduce the response payload size by only requesting what we need.
    // We could have used in a `bundle` field, but that gives us more image objects than we need.
    // Source: https://developers.giphy.com/docs/optional-settings/#fields-on-demand
    fields: string;
    q?: string;
    // only used in the search endpoint.
    lang?: string;
};

const giphy_result_schema = z.object({
    data: z.array(
        z.object({
            images: z.object({
                downsized_medium: z.object({
                    url: z.url(),
                }),
                fixed_height: z.object({
                    url: z.url(),
                }),
            }),
        }),
    ),
    pagination: z.object({
        total_count: z.number(),
        count: z.number(),
        offset: z.number(),
    }),
});

export class GiphyNetwork extends GifNetwork {
    static LIMIT = 15;
    is_loading_more = false;
    next_pos_identifier = 0;
    abandoned = false;

    get_provider(): GifProvider {
        return "giphy";
    }

    is_loading_more_gifs(): boolean {
        return this.is_loading_more;
    }

    abandon(): void {
        this.abandoned = true;
    }

    ask_for_default_gifs(next_page: boolean, render_gifs_callback: RenderGifsCallback): void {
        assert(!this.abandoned);
        // We use "default" generically here in anticipation of
        // tenor default == featured
        // giphy default == trending
        const data = get_base_payload();
        this.ask_for_gifs(`${BASE_URL}/trending`, data, next_page, render_gifs_callback);
    }

    ask_for_search_gifs(
        search_term: string,
        next_page: boolean,
        render_gifs_callback: RenderGifsCallback,
    ): void {
        assert(!this.abandoned);
        const data: GiphyPayload = {
            q: search_term,
            lang: user_settings.default_language,
            ...get_base_payload(),
        };

        this.ask_for_gifs(`${BASE_URL}/search`, data, next_page, render_gifs_callback);
    }

    ask_for_gifs(
        url: string,
        data: GiphyPayload,
        next_page = false,
        render_gifs_callback: RenderGifsCallback,
    ): void {
        assert(!this.abandoned);
        if (next_page) {
            this.is_loading_more = true;
            data = {...data, offset: this.next_pos_identifier};
        }
        void channel.get({
            url,
            data,
            success: (raw_tenor_result) => {
                // We don't want to have this code run after the caller
                // abandons its network object, to avoid all sorts of weird
                // bugs.
                if (this.abandoned) {
                    return;
                }
                const parsed_data = giphy_result_schema.parse(raw_tenor_result);
                const urls: GifInfoUrl[] = parsed_data.data.map((result) => ({
                    preview_url: result.images.fixed_height.url,
                    insert_url: result.images.downsized_medium.url,
                }));
                this.next_pos_identifier = parsed_data.pagination.offset + GiphyNetwork.LIMIT;
                this.is_loading_more = false;
                render_gifs_callback(urls, next_page);
            },
        });
    }
}

function get_base_payload(): GiphyPayload {
    return {
        api_key: realm.giphy_api_key,
        limit: GiphyNetwork.LIMIT,
        rating: get_rating(),
        offset: 0,
        // Source: https://developers.giphy.com/docs/api/schema#image-object
        // We will use the `downsized_medium` version for sending and `fixed_height` for
        // preview in the GIF picker.
        fields: "images.downsized_medium,images.fixed_height",
    };
}
