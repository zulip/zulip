import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$html_t, $t} from "../src/i18n.ts";
import render_stream_privacy from "./stream_privacy.ts";

export default function render_bookend(context) {
    const out = /* Client-side Handlebars template for rendering the trailing bookend. */ html`<div
        class="${to_bool(context.is_trailing_bookend)
            ? "trailing_bookend "
            : ""}bookend sub-unsub-message"
    >
        ${to_bool(context.is_spectator)
            ? html`
                  <span class="recent-topics-link">
                      <a href="#recent">${$t({defaultMessage: "Browse recent conversations"})}</a>
                  </span>
              `
            : html`
                  <span class="stream-status">
                      ${to_bool(context.deactivated)
                          ? html` ${$t({defaultMessage: "This channel has been archived."})} `
                          : to_bool(context.subscribed)
                            ? $html_t(
                                  {
                                      defaultMessage:
                                          "You subscribed to <z-stream-name></z-stream-name>. <channel-settings-link></channel-settings-link>",
                                  },
                                  {
                                      ["z-stream-name"]: () =>
                                          html`${{__html: render_stream_privacy(context)}}
                                          ${context.stream_name}`,
                                      ["channel-settings-link"]: () =>
                                          html` <a
                                              href="#channels/${context.stream_id}/${context.stream_name}/personal"
                                              >${$t({defaultMessage: "Manage channel settings"})}</a
                                          >`,
                                  },
                              )
                            : to_bool(context.just_unsubscribed)
                              ? $html_t(
                                    {
                                        defaultMessage:
                                            "You unsubscribed from <z-stream-name></z-stream-name>. <channel-settings-link></channel-settings-link>",
                                    },
                                    {
                                        ["z-stream-name"]: () =>
                                            html`${{__html: render_stream_privacy(context)}}
                                            ${context.stream_name}`,
                                        ["channel-settings-link"]: () =>
                                            html` <a
                                                href="#channels/${context.stream_id}/${context.stream_name}/general"
                                                >${$t({
                                                    defaultMessage: "View in channel settings",
                                                })}</a
                                            >`,
                                    },
                                )
                              : html`${$html_t(
                                    {
                                        defaultMessage:
                                            "You are not subscribed to <z-stream-name></z-stream-name>.",
                                    },
                                    {
                                        ["z-stream-name"]: () =>
                                            html`${{__html: render_stream_privacy(context)}}
                                            ${context.stream_name}`,
                                    },
                                )} `}
                  </span>
              `}
    </div> `;
    return to_html(out);
}
