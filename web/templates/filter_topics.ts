import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_input_wrapper from "./components/input_wrapper.ts";

export default function render_filter_topics() {
    const out = html`<div class="left-sidebar-filter-input-container">
        ${{
            __html: render_input_wrapper(
                {
                    input_button_icon: "close",
                    icon: "search",
                    custom_classes: "topic_search_section filter-topics has-input-pills",
                    input_type: "filter-input",
                },
                () => html`
                    <div
                        class="input-element home-page-input pill-container"
                        id="left-sidebar-filter-topic-input"
                    >
                        <div
                            class="input"
                            contenteditable="true"
                            id="topic_filter_query"
                            data-placeholder="${$t({defaultMessage: "Filter topics"})}"
                        ></div>
                    </div>
                `,
            ),
        }}
    </div> `;
    return to_html(out);
}
