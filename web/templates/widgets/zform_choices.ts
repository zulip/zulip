import {html, to_html} from "../../shared/src/html.ts";
import {to_array} from "../../src/hbs_compat.ts";

export default function render_zform_choices(context) {
    const out = html`<div class="widget-choices">
        <div class="widget-choices-heading">${context.heading}</div>
        <ul>
            ${to_array(context.choices).map(
                (choice) => html`
                    <li>
                        <button data-idx="${choice.idx}">${choice.short_name}</button>
                        &nbsp; ${choice.long_name}
                    </li>
                `,
            )}
        </ul>
    </div> `;
    return to_html(out);
}
