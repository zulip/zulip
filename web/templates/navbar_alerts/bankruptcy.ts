import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_bankruptcy(context) {
    const out = html`<div data-step="1">
            ${$t({defaultMessage: "Welcome back!"})}
            ${to_bool(context.old_unreads_missing)
                ? $html_t(
                      {
                          defaultMessage:
                              "You have <z-link>at least {unread_msgs_count}</z-link> unread messages.",
                      },
                      {
                          unread_msgs_count: context.unread_msgs_count,
                          ["z-link"]: (content) =>
                              html`<a
                                  href="/help/marking-messages-as-read"
                                  class="alert-link bankruptcy_unread_count"
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  >${content}</a
                              >`,
                      },
                  )
                : $html_t(
                      {
                          defaultMessage:
                              "You have <z-link>{unread_msgs_count}</z-link> unread messages.",
                      },
                      {
                          unread_msgs_count: context.unread_msgs_count,
                          ["z-link"]: (content) =>
                              html`<span class="bankruptcy_unread_count">${content}</span>`,
                      },
                  )}
            ${$t({defaultMessage: "Do you want to mark them all as read?"})}
            <span class="buttons">
                <a class="alert-link accept-bankruptcy" role="button" tabindex="0"
                    >${$t({defaultMessage: "Yes, please!"})}</a
                >
                &bull;
                <a class="alert-link exit" role="button" tabindex="0"
                    >${$t({defaultMessage: "No, I'll catch up."})}</a
                >
            </span>
        </div>
        <div data-step="2" style="display: none;">
            ${$t({defaultMessage: "Marking all messages as read…"})}
        </div> `;
    return to_html(out);
}
