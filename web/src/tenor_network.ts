import assert from "minimalistic-assert";
import * as z from "zod/mini";

import {type GifInfoUrl, GifNetwork, type RenderGifsCallback} from "./abstract_gif_network.ts";
import * as channel from "./channel.ts";
import {get_rating} from "./gif_state.ts";
import {realm} from "./state_data.ts";
import {user_settings} from "./user_settings.ts";

const BASE_URL = "https://tenor.googleapis.com/v2";

const tenor_rating_map = {
    // Source: https://developers.google.com/tenor/guides/content-filtering#ContentFilter-options
    pg: "medium",
    g: "high",
    r: "off",
    "pg-13": "low",
};

const tenor_result_schema = z.object({
    results: z.array(
        z.object({
            media_formats: z.object({
                tinygif: z.object({
                    url: z.url(),
                }),
                mediumgif: z.object({
                    url: z.url(),
                }),
            }),
        }),
    ),
    // This denotes the identifier to use for the next API call
    // to fetch the next set of results for the current query.
    next: z.string(),
});

export type TenorPayload = {
    key: string;
    client_key: string;
    limit: string;
    media_filter: string;
    locale: string;
    contentfilter: string;
    pos?: string | number | undefined;
    q?: string;
};

export class TenorNetwork extends GifNetwork {
    is_loading_more = false;
    next_pos_identifier: string | number | undefined;
    abandoned = false;

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
        this.ask_for_gifs(`${BASE_URL}/featured`, data, next_page, render_gifs_callback);
    }

    ask_for_search_gifs(
        search_term: string,
        next_page: boolean,
        render_gifs_callback: RenderGifsCallback,
    ): void {
        assert(!this.abandoned);
        const data: TenorPayload = {
            q: search_term,
            ...get_base_payload(),
        };

        this.ask_for_gifs(`${BASE_URL}/search`, data, next_page, render_gifs_callback);
    }

    ask_for_gifs(
        url: string,
        data: TenorPayload,
        next_page = false,
        render_gifs_callback: RenderGifsCallback,
    ): void {
        assert(!this.abandoned);
        if (next_page) {
            this.is_loading_more = true;
            data = {...data, pos: this.next_pos_identifier};
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
                const parsed_data = tenor_result_schema.parse(raw_tenor_result);
                const urls: GifInfoUrl[] = parsed_data.results.map((result) => ({
                    preview_url: result.media_formats.tinygif.url,
                    insert_url: result.media_formats.mediumgif.url,
                }));
                this.next_pos_identifier = parsed_data.next;
                this.is_loading_more = false;
                render_gifs_callback(urls, next_page);
            },
        });
    }
}

function get_base_payload(): TenorPayload {
    return {
        key: realm.tenor_api_key,
        client_key: "ZulipWeb",
        limit: "15",
        // We use the tinygif size for the picker UI, and the mediumgif size
        // for what gets actually uploaded.
        media_filter: "tinygif,mediumgif",
        locale: user_settings.default_language,
        contentfilter: tenor_rating_map[get_rating()],
    };
}
