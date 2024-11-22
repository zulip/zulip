import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_group_setting_value_pill_input(context) {
    const out = html`<div class="input-group">
        <label class="group-setting-label">
            ${context.label}
            ${to_bool(context.label_parens_text) ? html`(<i>${context.label_parens_text}</i>)` : ""}
        </label>
        <div
            class="pill-container person_picker prop-element"
            id="${to_bool(context.prefix) ? context.prefix : "id_"}${context.setting_name}"
            data-setting-widget-type="group-setting-type"
        >
            <div
                class="input"
                contenteditable="true"
                data-placeholder="${$t({defaultMessage: "Add roles, groups or users"})}"
            ></div>
        </div>
    </div> `;
    return to_html(out);
}
