import {html, to_html} from "../../../src/html.ts";
import {$t} from "../../../src/i18n.ts";
import render_input_wrapper from "../input_wrapper.ts";

export default function render_filter_input() {
    const out = {
        __html: render_input_wrapper(
            {input_button_icon: "close", icon: "search", input_type: "filter-input"},
            () => html`
                <input
                    class="input-element"
                    type="text"
                    placeholder="${$t({defaultMessage: "Filter component"})}"
                />
            `,
        ),
    };
    return to_html(out);
}
