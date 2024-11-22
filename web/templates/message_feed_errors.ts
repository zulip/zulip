import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$html_t} from "../src/i18n.ts";

export default function render_message_feed_errors(context) {
    const out = html`<div class="history-limited-box">
            <p>
                <i class="fa fa-exclamation-circle" aria-hidden="true"></i>
                ${$html_t(
                    {
                        defaultMessage:
                            "Some older messages are unavailable. <z-link>Upgrade your organization</z-link> to access your full message history.",
                    },
                    {
                        ["z-link"]: (content) =>
                            html`<a href="/plans/" target="_blank" rel="noopener noreferrer"
                                >${content}</a
                            >`,
                    },
                )}
            </p>
        </div>
        <div class="all-messages-search-caution hidden-for-spectators" hidden>
            <p>
                <i
                    class="all-messages-search-caution-icon fa fa-exclamation-circle"
                    aria-hidden="true"
                ></i>
                ${$html_t(
                    {defaultMessage: "End of results from your <z-link>history</z-link>."},
                    {
                        ["z-link"]: (content) =>
                            html`<a
                                href="/help/search-for-messages#searching-shared-history"
                                target="_blank"
                                rel="noopener noreferrer"
                                >${content}</a
                            >`,
                    },
                )}
                &nbsp;
                <span>
                    ${to_bool(context.is_guest)
                        ? $html_t(
                              {
                                  defaultMessage:
                                      "Consider <z-link>searching all public channels that you can view</z-link>.",
                              },
                              {
                                  ["z-link"]: (content) =>
                                      html`<a class="search-shared-history" href="">${content}</a>`,
                              },
                          )
                        : $html_t(
                              {
                                  defaultMessage:
                                      "Consider <z-link>searching all public channels</z-link>.",
                              },
                              {
                                  ["z-link"]: (content) =>
                                      html`<a class="search-shared-history" href="">${content}</a>`,
                              },
                          )}
                </span>
            </p>
        </div>
        <div class="empty_feed_notice_main"></div> `;
    return to_html(out);
}
