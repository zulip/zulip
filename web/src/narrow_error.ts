import render_empty_feed_notice from "../templates/empty_feed_notice.hbs";

import type {EmojiRenderingDetails} from "./emoji.ts";

type QueryWord = {
    query_word: string;
    is_stop_word: boolean;
};

export type SearchData = {
    query_words: QueryWord[];
    has_stop_word: boolean;
};

export type NarrowBannerData = {
    title: string;
    html?: string;
    search_data?: SearchData;
    reaction_emoji?: EmojiRenderingDetails & {
        emoji_alt_code: boolean;
        is_realm_emoji: boolean;
    };
};

export function narrow_error(narrow_banner_data: NarrowBannerData): string {
    const title = narrow_banner_data.title;
    const notice_html = narrow_banner_data.html;
    const search_data = narrow_banner_data.search_data;
    const reaction_emoji = narrow_banner_data.reaction_emoji;

    const empty_feed_notice = render_empty_feed_notice({
        title,
        notice_html,
        search_data,
        reaction_emoji,
    });
    return empty_feed_notice;
}
