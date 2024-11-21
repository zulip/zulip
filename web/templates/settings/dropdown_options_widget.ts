import {to_array} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";

export default function render_dropdown_options_widget(context) {
    const out = to_array(context.option_values).map(
        (option) => html` <option value="${option.code}">${option.description}</option> `,
    );
    return to_html(out);
}
