import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_confirm_unsubscribe_private_stream(context) {
    const out = html`${!to_bool(context.unsubscribing_other_user)
        ? html`
              <p>
                  ${$t({
                      defaultMessage:
                          "Once you leave this channel, you will not be able to rejoin.",
                  })}
              </p>
          `
        : ""}${to_bool(context.organization_will_lose_content_access)
        ? html`
              <p>
                  ${$t({
                      defaultMessage:
                          "Your organization will lose access content in this channel, and nobody will be able to subscribe to it in the future.",
                  })}
              </p>
          `
        : ""}`;
    return to_html(out);
}
