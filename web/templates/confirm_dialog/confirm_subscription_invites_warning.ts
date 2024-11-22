import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_confirm_subscription_invites_warning(context) {
    const out = html`<p>
        ${$t(
            {
                defaultMessage:
                    "Are you sure you want to create channel ''''{channel_name}'''' and subscribe {count} users to it?",
            },
            {channel_name: context.channel_name, count: context.count},
        )}
    </p> `;
    return to_html(out);
}
