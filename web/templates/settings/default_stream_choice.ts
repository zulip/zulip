import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_icon_button from "../components/icon_button.ts";
import render_dropdown_widget from "../dropdown_widget.ts";

export default function render_default_stream_choice(context) {
    const out = html`<div class="choice-row" data-value="${context.value}">
        ${{
            __html: render_dropdown_widget({
                default_text: $t({defaultMessage: "Select channel"}),
                widget_name: context.stream_dropdown_widget_name,
            }),
        }}
        ${{
            __html: render_icon_button({
                ["aria-label"]: $t({defaultMessage: "Delete"}),
                ["data-tippy-content"]: $t({defaultMessage: "Delete"}),
                icon: "trash",
                custom_classes: "delete-choice tippy-zulip-delayed-tooltip",
                intent: "danger",
            }),
        }}
    </div> `;
    return to_html(out);
}
