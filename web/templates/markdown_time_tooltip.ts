import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_markdown_time_tooltip(context) {
    const out = html`${$t({defaultMessage: "Everyone sees this in their own time zone."})}
        <br />
        ${$t({defaultMessage: "Your time zone:"})} ${context.tz_offset_str} `;
    return to_html(out);
}
