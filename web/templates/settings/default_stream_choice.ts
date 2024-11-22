import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_dropdown_widget from "../dropdown_widget.ts";

export default function render_default_stream_choice(context) {
    const out = html`<div class="choice-row" data-value="${context.value}">
        ${{
            __html: render_dropdown_widget({
                default_text: $t({defaultMessage: "Select channel"}),
                widget_name: context.stream_dropdown_widget_name,
            }),
        }}
        <button
            type="button"
            class="button rounded small delete-choice tippy-zulip-delayed-tooltip"
            data-tippy-content="${$t({defaultMessage: "Delete"})}"
        >
            <i class="fa fa-trash-o" aria-hidden="true"></i>
        </button>
    </div> `;
    return to_html(out);
}
