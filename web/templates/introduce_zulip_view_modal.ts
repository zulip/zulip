import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$html_t, $t} from "../src/i18n.ts";

export default function render_introduce_zulip_view_modal(context) {
    const out = html`<div id="introduce-zulip-view-modal">
    <p>
${
    context.zulip_view === "inbox"
        ? html`
              ${$html_t({
                  defaultMessage:
                      "You’ll see a list of <b>conversations</b> where you have <b>unread messages</b>, organized by channel.",
              })}
          `
        : context.zulip_view === "recent_conversations"
          ? html`
                ${$html_t({defaultMessage: "You’ll see a list of <b>ongoing conversations</b>."})}
            `
          : ""
}        ${$html_t({defaultMessage: "Each conversation is <b>labeled with a topic</b> by the person who started it."})}
    </p>
    <p>
        ${$t({defaultMessage: "Click on a conversation to view it. To return here, you can:"})}
        <ul>
            <li>${$html_t({defaultMessage: "Use the <b>back</b> button in your browser or desktop app."})}</li>
            <li>
${context.zulip_view === "inbox" ? $html_t({defaultMessage: "Click <z-icon-inbox></z-icon-inbox> <b>Inbox</b> in the left sidebar."}, {["z-icon-inbox"]: () => html`<i class="zulip-icon zulip-icon-inbox" aria-hidden="true"></i>`}) : context.zulip_view === "recent_conversations" ? html`${$html_t({defaultMessage: "Click <z-icon-recent></z-icon-recent> <b>Recent conversations</b> in the left sidebar."}, {["z-icon-recent"]: () => html`<i class="zulip-icon zulip-icon-recent" aria-hidden="true"></i>`})} ` : ""}            </li>
${
    to_bool(context.current_home_view_and_escape_navigation_enabled)
        ? html`
              <li>
                  ${$html_t(
                      {defaultMessage: "Use <z-button>Esc</z-button> to go to your home view."},
                      {
                          ["z-button"]: (content) =>
                              html`<span class="keyboard-button">${content}</span>`,
                      },
                  )}
              </li>
          `
        : ""
}        </ul>
    </p>
</div>
`;
    return to_html(out);
}
