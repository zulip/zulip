import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t, $t} from "../../src/i18n.ts";

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
        : ""}${to_bool(context.display_stream_archive_warning)
        ? html`
              <p>
                  ${to_bool(context.unsubscribing_other_user)
                      ? $html_t(
                            {
                                defaultMessage:
                                    "Because you are removing the last subscriber from a private channel, it will be automatically <z-link>archived</z-link>.",
                            },
                            {
                                ["z-link"]: (content) =>
                                    html`<a
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        href="/help/archive-a-channel"
                                        >${content}</a
                                    >`,
                            },
                        )
                      : $html_t(
                            {
                                defaultMessage:
                                    "Because you are the only subscriber, this channel will be automatically <z-link>archived</z-link>.",
                            },
                            {
                                ["z-link"]: (content) =>
                                    html`<a
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        href="/help/archive-a-channel"
                                        >${content}</a
                                    >`,
                            },
                        )}
              </p>
          `
        : ""}`;
    return to_html(out);
}
