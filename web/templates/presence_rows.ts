import {html, to_html} from "../shared/src/html.ts";
import {to_array} from "../src/hbs_compat.ts";
import render_presence_row from "./presence_row.ts";

export default function render_presence_rows(context) {
    const out = to_array(context.presence_rows).map(
        (row) => html` ${{__html: render_presence_row(row)}}`,
    );
    return to_html(out);
}
