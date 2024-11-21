import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_topic_list_new_topic(context) {
    const out = html`<li class="bottom_left_row topic-list-item">
        <a class="zoomed-new-topic" data-stream-id="${context.stream_id}" href="">
            <i
                class="topic-list-new-topic-icon zulip-icon zulip-icon-square-plus"
                aria-hidden="true"
            ></i>
            <span class="new-topic-label">${$t({defaultMessage: "NEW TOPIC"})}</span>
        </a>
    </li> `;
    return to_html(out);
}
