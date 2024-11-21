import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_stream_can_subscribe_group_label(context) {
    const out = html`${$t({defaultMessage: "Who can subscribe to this channel"})}
    ${!to_bool(context.is_invite_only)
        ? html`<i
              >(${$t({
                  defaultMessage: "everyone except guests can subscribe to any public channel",
              })})</i
          > `
        : ""}`;
    return to_html(out);
}
