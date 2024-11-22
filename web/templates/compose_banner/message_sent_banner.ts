import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";

export default function render_message_sent_banner(context) {
    const out = html`<div
        class="above_compose_banner main-view-banner success ${context.classname}"
    >
        <p class="banner_content">
            ${context.banner_text}
            ${to_bool(context.link_text)
                ? html` <a
                      class="above_compose_banner_action_link"
                      ${to_bool(context.above_composebox_narrow_url)
                          ? html`href="${context.above_composebox_narrow_url}"`
                          : ""}
                      data-message-id="${context.link_msg_id}"
                      >${context.link_text}</a
                  >`
                : ""}
        </p>
        <a role="button" class="zulip-icon zulip-icon-close main-view-banner-close-button"></a>
    </div> `;
    return to_html(out);
}
