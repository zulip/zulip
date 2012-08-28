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
    html?: string;
    show_action?: boolean;
    search_data?: SearchData;
} & ({title: string} | {title_html: string});

export function narrow_error(narrow_banner_data: NarrowBannerData): string {
    return render_empty_feed_notice({
        ...narrow_banner_data,
        notice_html: narrow_banner_data.html,
    });
}
