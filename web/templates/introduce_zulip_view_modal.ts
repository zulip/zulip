import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$html_t, $t} from "../src/i18n.ts";

export default function render_introduce_zulip_view_modal(context) {
    const out = html`<div id="introduce-zulip-view-modal">
        <p>
            ${context.zulip_view === "inbox"
                ? $html_t(
                      {
                          defaultMessage:
                              "You’ll see a list of <z-highlight>conversations</z-highlight> where you have <z-highlight>unread messages</z-highlight>, organized by channel.",
                      },
                      {
                          ["z-highlight"]: (content) =>
                              html`<b class="highlighted-element">${content}</b>`,
                      },
                  )
                : context.zulip_view === "recent_conversations"
                  ? html`${$html_t(
                        {
                            defaultMessage:
                                "You’ll see a list of <z-highlight>ongoing conversations</z-highlight>.",
                        },
                        {
                            ["z-highlight"]: (content) =>
                                html`<b class="highlighted-element">${content}</b>`,
                        },
                    )} `
                  : ""}
            ${$html_t(
                {
                    defaultMessage:
                        "Each conversation is <z-highlight>labeled with a topic</z-highlight> by the person who started it.",
                },
                {["z-highlight"]: (content) => html`<b class="highlighted-element">${content}</b>`},
            )}
        </p>
        <p>
            ${$t({defaultMessage: "Click on a conversation to view it. To return here, you can:"})}
        </p>
        <ul>
            <li>
                ${$html_t(
                    {
                        defaultMessage:
                            "Use the <z-highlight>back</z-highlight> button in your browser or desktop app.",
                    },
                    {
                        ["z-highlight"]: (content) =>
                            html`<b class="highlighted-element">${content}</b>`,
                    },
                )}
            </li>
            <li>
                ${context.zulip_view === "inbox"
                    ? $html_t(
                          {
                              defaultMessage:
                                  "Click <z-icon-inbox></z-icon-inbox> <z-highlight>Inbox</z-highlight> in the left sidebar.",
                          },
                          {
                              ["z-icon-inbox"]: () =>
                                  html`<i
                                      class="zulip-icon zulip-icon-inbox"
                                      aria-hidden="true"
                                  ></i>`,
                              ["z-highlight"]: (content) =>
                                  html`<b class="highlighted-element">${content}</b>`,
                          },
                      )
                    : context.zulip_view === "recent_conversations"
                      ? html`${$html_t(
                            {
                                defaultMessage:
                                    "Click <z-icon-recent></z-icon-recent> <z-highlight>Recent conversations</z-highlight> in the left sidebar.",
                            },
                            {
                                ["z-icon-recent"]: () =>
                                    html`<i
                                        class="zulip-icon zulip-icon-recent"
                                        aria-hidden="true"
                                    ></i>`,
                                ["z-highlight"]: (content) =>
                                    html`<b class="highlighted-element">${content}</b>`,
                            },
                        )} `
                      : ""}
            </li>
            ${to_bool(context.current_home_view_and_escape_navigation_enabled)
                ? html`
                      <li>
                          ${$html_t(
                              {
                                  defaultMessage:
                                      "Use <z-button>Esc</z-button> to go to your home view.",
                              },
                              {
                                  ["z-button"]: (content) =>
                                      html`<span class="keyboard-button">${content}</span>`,
                              },
                          )}
                      </li>
                  `
                : ""}
        </ul>
    </div> `;
    return to_html(out);
}
