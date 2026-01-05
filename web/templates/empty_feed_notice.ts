import {to_array, to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_empty_feed_notice(context) {
    const out = html`<div class="empty_feed_notice">
        <h4 class="empty-feed-notice-title">${context.title}</h4>
        ${to_bool(context.search_data)
            ? to_bool(context.search_data.has_stop_word)
                ? html`
                      <div class="empty-feed-notice-description">
                          ${$t({defaultMessage: "Common words were excluded from your search:"})}
                          <br />
                          ${to_array(context.search_data.query_words).map((word) =>
                              to_bool(word.is_stop_word)
                                  ? html` <del>${word.query_word}</del> `
                                  : html`
                                        <span class="search-query-word">${word.query_word}</span>
                                    `,
                          )}
                      </div>
                  `
                : ""
            : to_bool(context.notice_html)
              ? html`
                    <div class="empty-feed-notice-description">
                        ${{__html: context.notice_html}}
                    </div>
                `
              : ""}
    </div> `;
    return to_html(out);
}
