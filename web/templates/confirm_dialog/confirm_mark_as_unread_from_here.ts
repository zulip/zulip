import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_confirm_mark_as_unread_from_here(context) {
    const out = html`<p>
        ${to_bool(context.show_message_count)
            ? html`
                  ${$t(
                      {
                          defaultMessage:
                              "Are you sure you want to mark {count} messages as unread? Messages in multiple conversations may be affected.",
                      },
                      {count: context.count},
                  )}
              `
            : html`
                  ${$t({
                      defaultMessage:
                          "Are you sure you want to mark messages as unread? Messages in multiple conversations may be affected.",
                  })}
              `}
    </p> `;
    return to_html(out);
}
