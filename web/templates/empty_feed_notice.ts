import {html, to_html} from "../shared/src/html.ts";
import {to_array, to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_empty_feed_notice(context) {
    const out = html`<div class="empty_feed_notice">
        <h4 class="empty-feed-notice-title">${context.title}</h4>
        <div class="empty-feed-notice-description">
            ${to_bool(context.search_data)
                ? html` ${to_bool(context.search_data.has_stop_word)
                      ? html`${$t({
                                defaultMessage: "Some common words were excluded from your search.",
                            })} <br />`
                      : ""}${$t({defaultMessage: "You searched for:"})}
                  ${to_bool(context.search_data.stream_query)
                      ? html` <span>stream: ${context.search_data.stream_query}</span> `
                      : ""}${to_bool(context.search_data.topic_query)
                      ? html` <span>topic: ${context.search_data.topic_query}</span> `
                      : ""}${to_array(context.search_data.query_words).map((word) =>
                      to_bool(word.is_stop_word)
                          ? html` <del>${word.query_word}</del> `
                          : html` <span>${word.query_word}</span> `,
                  )}`
                : html` ${{__html: context.html}} `}
        </div>
    </div> `;
    return to_html(out);
}
