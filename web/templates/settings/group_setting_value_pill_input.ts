import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";

export default function render_group_setting_value_pill_input(context) {
    const out = html`<div class="input-group ${context.setting_name}_container">
        ${
            /* We are using snake case for one of the classes since setting_name
    is always in snake case and it would be weird to have the resultant id
    be a mix of two types of cases. */ ""
        }
        <label class="group-setting-label ${context.setting_name}_label">
            ${context.label}
            ${to_bool(context.label_parens_text) ? html`(<i>${context.label_parens_text}</i>)` : ""}
            ${to_bool(context.help_link)
                ? html` ${{__html: render_help_link_widget({link: context.help_link})}}`
                : ""}
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
