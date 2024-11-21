import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";

export default function render_information_density_update_button_tooltip(context) {
    const out = html`<div id="information_density_tooltip_template">
        <div class="tooltip-inner-content">
            <span>
                ${context.tooltip_first_line}
                ${to_bool(context.tooltip_second_line)
                    ? html`
                          <br />
                          <i>${context.tooltip_second_line}</i>
                      `
                    : ""}
            </span>
        </div>
    </div> `;
    return to_html(out);
}
