import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import render_dropdown_widget from "./dropdown_widget.ts";
import render_help_link_widget from "./help_link_widget.ts";

export default function render_dropdown_widget_with_label(context) {
    const out = html`<div class="input-group" id="${context.widget_name}_widget_container">
        <label class="settings-field-label" for="${context.widget_name}_widget"
            >${context.label}
            ${to_bool(context.help_link)
                ? {__html: render_help_link_widget({link: context.help_link})}
                : ""}
        </label>
        <span
            class="prop-element hide"
            id="id_${context.widget_name}"
            data-setting-widget-type="dropdown-list-widget"
            ${to_bool(context.value_type)
                ? html`data-setting-value-type="${context.value_type}"`
                : ""}
        ></span>
        <div class="dropdown_widget_with_label_wrapper">
            ${{__html: render_dropdown_widget(context)}}
        </div>
    </div> `;
    return to_html(out);
}
