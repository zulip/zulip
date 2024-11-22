import {html, to_html} from "../shared/src/html.ts";
import {to_array, to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import render_message_reaction from "./message_reaction.ts";

export default function render_message_reactions(context) {
    const out = html`<div class="message_reactions">
        ${to_array(context.msg.message_reactions).map(
            (reaction) =>
                html` ${{
                    __html: render_message_reaction({
                        is_archived: context.is_archived,
                        ...reaction,
                    }),
                }}`,
        )}${!to_bool(context.is_archived)
            ? html`
                  <div
                      class="reaction_button"
                      role="button"
                      aria-haspopup="true"
                      data-tooltip-template-id="add-emoji-tooltip-template"
                      aria-label="${$t({defaultMessage: "Add emoji reaction"})} (:)"
                  >
                      <div class="emoji-message-control-button-container">
                          <i class="zulip-icon zulip-icon-smile" tabindex="0"></i>
                          <div class="message_reaction_count">+</div>
                      </div>
                  </div>
              `
            : ""}
    </div> `;
    return to_html(out);
}
