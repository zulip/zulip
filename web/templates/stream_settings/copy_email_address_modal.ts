import {to_array} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_dropdown_widget_with_label from "../dropdown_widget_with_label.ts";

export default function render_copy_email_address_modal(context) {
    const out = html`<div class="copy-email-modal">
        ${{
            __html: render_dropdown_widget_with_label({
                label: $t({
                    defaultMessage:
                        "Who should be the sender of the Zulip messages for this email address?",
                }),
                widget_name: "sender_channel_email_address",
            }),
        }}
        <p class="question-which-parts">
            ${$t({
                defaultMessage:
                    "Which parts of the emails should be included in the Zulip messages?",
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
                        <label class="inline" for="${tag.name}">${tag.description}</label>
                    </div> `,
        )}
        <hr />
        <p class="stream-email-header">${$t({defaultMessage: "Channel email address:"})}</p>
        <div class="stream-email">
            <div class="email-address">${context.email_address}</div>
            <span
                class="copy-button tippy-zulip-tooltip copy-email-address"
                data-tippy-content="${$t({defaultMessage: "Copy email address"})}"
                data-clipboard-text="${context.email_address}"
            >
                <i class="zulip-icon zulip-icon-copy"></i>
            </span>
        </div>
    </div> `;
    return to_html(out);
}
