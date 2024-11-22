import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_user_full_name(context) {
    const out = to_bool(context.should_add_guest_user_indicator)
        ? html`<span class="user-name">${context.name}</span>&nbsp;<i class="guest-indicator"
                  >(${$t({defaultMessage: "guest"})})</i
              > `
        : html`<span class="user-name">${context.name}</span> `;
    return to_html(out);
}
