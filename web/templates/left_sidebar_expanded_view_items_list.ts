import {to_array} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import render_left_sidebar_expanded_view_item from "./left_sidebar_expanded_view_item.ts";

export default function render_left_sidebar_expanded_view_items_list(context) {
    const out = to_array(context.expanded_views).map(
        (view) => html` ${{__html: render_left_sidebar_expanded_view_item(view)}}`,
    );
    return to_html(out);
}
