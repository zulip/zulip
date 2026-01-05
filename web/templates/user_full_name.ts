import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_user_full_name(context) {
    const out = html`${to_bool(context.should_add_guest_user_indicator)
        ? html`<span class="user-name">${context.name}</span>&nbsp;<i class="guest-indicator"
                  >(${$t({defaultMessage: "guest"})})</i
              > `
        : to_bool(context.is_hidden)
          ? html`<span class="user-name muted">${$t({defaultMessage: "Muted user"})}</span> `
          : html`<span class="user-name">${context.name}</span> `}${to_bool(context.is_current_user)
        ? html`&nbsp;<span class="my_user_status">${$t({defaultMessage: "(you)"})}</span>`
        : ""} `;
    return to_html(out);
}
