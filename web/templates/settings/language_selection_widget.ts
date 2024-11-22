import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";

export default function render_language_selection_widget(context) {
    const out = html`<div
        class="language_selection_widget input-group prop-element"
        id="id_${context.section_name}"
        data-setting-widget-type="language-setting"
    >
        <label class="settings-field-label" for="id_language_selection_button">
            ${context.section_title}
            ${to_bool(context.help_link_widget_link)
                ? html` ${{__html: render_help_link_widget({link: context.help_link_widget_link})}}`
                : ""}
        </label>
        <button
            type="button"
            id="id_language_selection_button"
            class="language_selection_button button rounded tippy-zulip-delayed-tooltip"
            data-section="${context.section_name}"
            data-tippy-content="${$t({defaultMessage: "Change language"})}"
        >
            <span class="${context.section_name}" data-language-code="${context.language_code}"
                >${context.setting_value}</span
            >
        </button>
    </div> `;
    return to_html(out);
}
