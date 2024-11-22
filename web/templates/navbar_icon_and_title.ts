import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_navbar_icon_and_title(context) {
    const out = html`${to_bool(context.zulip_icon)
            ? html`<i
                  class="navbar-icon zulip-icon zulip-icon-${context.zulip_icon}"
                  aria-hidden="true"
              ></i> `
            : to_bool(context.icon)
              ? html`<i class="navbar-icon fa fa-${context.icon}" aria-hidden="true"></i> `
              : ""}<span class="message-header-navbar-title">${context.title}</span> ${to_bool(
            context.stream,
        )
            ? to_bool(context.stream.is_archived)
                ? html`
                      <span class="message-header-archived">
                          <i class="archived-indicator">(${$t({defaultMessage: "archived"})})</i>
                      </span>
                  `
                : ""
            : ""}`;
    return to_html(out);
}
