import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_resolve_topic_time_limit_error_modal(context) {
    const out = html`<p>
        ${context.resolve_topic_time_limit_error_string}
        ${to_bool(context.topic_is_resolved)
            ? html` ${$t({defaultMessage: "Contact a moderator to unresolve this topic."})} `
            : html` ${$t({defaultMessage: "Contact a moderator to resolve this topic."})} `}
    </p> `;
    return to_html(out);
}
