import {html, to_html} from "../../shared/src/html.ts";
import {to_array} from "../../src/hbs_compat.ts";
import render_browse_streams_list_item from "./browse_streams_list_item.ts";

export default function render_browse_streams_list(context) {
    const out = to_array(context.subscriptions).map(
        (sub) => html` ${{__html: render_browse_streams_list_item(sub)}}`,
    );
    return to_html(out);
}
