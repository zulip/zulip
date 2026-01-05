import {tooltip_hotkey_hints} from "../../src/common.ts";
import {html, to_html} from "../../src/html.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_title_tooltip(context) {
    const out = html`${$html_t(
        {defaultMessage: "Filter {total_user_count, plural, =1 {1 person} other {# people}}"},
        {total_user_count: context.total_user_count},
    )}${tooltip_hotkey_hints("W")} `;
    return to_html(out);
}
