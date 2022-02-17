import render_empty_feed_notice from "../templates/empty_feed_notice.hbs";

export function narrow_error(narrow_banner_data) {
    const title = narrow_banner_data.title;
    const html = narrow_banner_data.html;
    const search_data = narrow_banner_data.search_data;

    const $empty_feed_notice = render_empty_feed_notice({title, html, search_data});
    return $empty_feed_notice;
}
