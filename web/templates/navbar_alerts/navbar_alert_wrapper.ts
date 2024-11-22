import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_navbar_alert_wrapper(context) {
    const out = html`<div
        data-process="${context.data_process}"
        class="alert alert-info ${to_bool(context.custom_class) ? context.custom_class : ""}"
    >
        ${{__html: context.rendered_alert_content_html}}
        <span
            class="close"
            data-dismiss="alert"
            aria-label="${$t({defaultMessage: "Close"})}"
            role="button"
            tabindex="0"
            >&times;</span
        >
    </div> `;
    return to_html(out);
}
