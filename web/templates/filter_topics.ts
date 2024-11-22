import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_filter_topics() {
    const out = html`<div class="topic_search_section filter-topics">
        <input
            class="topic-list-filter home-page-input filter_text_input"
            id="filter-topic-input"
            type="text"
            autocomplete="off"
            placeholder="${$t({defaultMessage: "Filter topics"})}"
        />
        <button
            type="button"
            class="bootstrap-btn clear_search_button"
            id="clear_search_topic_button"
        >
            <i class="fa fa-remove" aria-hidden="true"></i>
        </button>
    </div> `;
    return to_html(out);
}
