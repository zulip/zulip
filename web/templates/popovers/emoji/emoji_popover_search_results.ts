import {to_array} from "../../../src/hbs_compat.ts";
import {html, to_html} from "../../../src/html.ts";
import render_emoji_popover_emoji from "./emoji_popover_emoji.ts";

export default function render_emoji_popover_search_results(context) {
    const out = to_array(context.search_results).map(
        (result, result_index) =>
            html` ${{
                __html: render_emoji_popover_emoji({
                    emoji_dict: result,
                    index: result_index,
                    section: "0",
                    type: "emoji_search_result",
                }),
            }}`,
    );
    return to_html(out);
}
