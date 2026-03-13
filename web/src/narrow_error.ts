import render_empty_feed_notice from "../templates/empty_feed_notice.hbs";

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
    title_html?: string;
    html?: string;
    show_action?: boolean;
    search_data?: SearchData;
};

export function narrow_error(narrow_banner_data: NarrowBannerData): string {
    const title = narrow_banner_data.title;
    const title_html = narrow_banner_data.title_html;
    const notice_html = narrow_banner_data.html;
    const search_data = narrow_banner_data.search_data;
    const show_action = narrow_banner_data.show_action;

    const empty_feed_notice = render_empty_feed_notice({
        title,
        title_html,
        notice_html,
        search_data,
        show_action,
    });
    return empty_feed_notice;
}
