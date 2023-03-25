import render_empty_feed_notice from "../templates/empty_feed_notice.hbs";

type NarrowBannerData = {
    html?: string;
    search_data?: {
        query_words: string[];
        has_stop_word: boolean;
    };
    title: string;
};

export function narrow_error(narrow_banner_data: NarrowBannerData): string {
    const html = narrow_banner_data.html;
    const search_data = narrow_banner_data.search_data;
    const title = narrow_banner_data.title;

    const empty_feed_notice = render_empty_feed_notice({title, html, search_data});

    return empty_feed_notice;
}
