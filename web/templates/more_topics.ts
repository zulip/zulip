import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_more_topics(context) {
    const out = html`<li
        class="topic-list-item show-more-topics bottom_left_row
  ${!to_bool(context.more_topics_unreads) ? "zero-topic-unreads" : ""}
  ${to_bool(context.more_topics_unread_count_muted) ? "more_topic_unreads_muted_only" : ""}"
    >
        <div class="topic-box">
            <a class="sidebar-topic-action-heading" tabindex="0"
                >${$t({defaultMessage: "Show all topics"})}</a
            >
            <div class="topic-markers-and-unreads">
                ${to_bool(context.more_topics_have_unread_mention_messages)
                    ? html` <span class="unread_mention_info"> @ </span> `
                    : ""}
                <span
                    class="unread_count ${!to_bool(context.more_topics_unreads)
                        ? "zero_count"
                        : ""}"
                >
                    ${context.more_topics_unreads}
                </span>
            </div>
        </div>
    </li> `;
    return to_html(out);
}
