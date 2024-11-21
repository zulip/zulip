import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_stream_list_section_container(context) {
    const out = html`<div
        id="stream-list-${context.id}-container"
        data-section-id="${context.id}"
        class="stream-list-section-container"
    >
        <div class="stream-list-subsection-header zoom-in-hide">
            <i
                class="stream-list-section-toggle zulip-icon zulip-icon-heading-triangle-right rotate-icon-down"
                aria-hidden="true"
            ></i>
            <h4 class="left-sidebar-title">${context.section_title}</h4>
            ${to_bool(context.plus_icon_url)
                ? html`
                      <a
                          href="${context.plus_icon_url}"
                          class="add-stream-tooltip add-stream-icon-container hidden-for-spectators"
                          data-tippy-content="${$t({defaultMessage: "Create a channel"})}"
                      >
                          <i
                              class="add_stream_icon zulip-icon zulip-icon-square-plus"
                              aria-hidden="true"
                          ></i>
                      </a>
                  `
                : ""}
            <div class="markers-and-unreads">
                <span class="unread_mention_info"></span>
                <span class="unread_count normal-count"></span>
                <span class="masked_unread_count">
                    <i class="zulip-icon zulip-icon-masked-unread"></i>
                </span>
            </div>
        </div>
        <ul id="stream-list-${context.id}" class="stream-list-section"></ul>
    </div> `;
    return to_html(out);
}
