import {html, to_html} from "../../shared/src/html.ts";
import {to_array} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_copy_email_address_modal(context) {
    const out = html`<div class="copy-email-modal">
        <p class="question-which-parts">
            ${$t({
                defaultMessage:
                    "Which parts of the email should be included in the Zulip message sent to this channel?",
            })}
        </p>
        ${to_array(context.tags).map(
            (tag) =>
                html`${tag.name === "prefer-html" ? html` <hr /> ` : ""}
                    <div class="input-group" id="${tag.name}-input-group">
                        <label class="checkbox">
                            <input class="tag-checkbox" id="${tag.name}" type="checkbox" />
                            <span class="rendered-checkbox"></span>
                        </label>
                        <label class="inline" for="${tag.name}">${{__html: tag.description}}</label>
                    </div> `,
        )}
        <hr />
        <p class="stream-email-header">${$t({defaultMessage: "Channel email address:"})}</p>
        <div class="stream-email">
            <div class="email-address">${context.email_address}</div>
        </div>
    </div> `;
    return to_html(out);
}
