import {to_bool} from "../../../src/hbs_compat.ts";
import {html, to_html} from "../../../src/html.ts";

export default function render_left_sidebar_view_popover_item(context) {
    const out = html`<li
        role="none"
        class="link-item popover-menu-list-item views-popover-menu-${context.css_class_suffix}"
    >
        <a
            href="#${context.fragment}"
            role="menuitem"
            class="popover-menu-link tippy-left-sidebar-tooltip"
            data-tooltip-template-id="${context.tooltip_template_id}"
            tabindex="0"
        >
            <i class="popover-menu-icon zulip-icon ${context.icon}" aria-hidden="true"></i>
            ${to_bool(context.has_unread_count)
                ? html`
                      <span class="label-and-unread-wrapper">
                          <span class="popover-menu-label">${context.name}</span>
                          <span class="unread_count ${context.unread_count_type}"
                              >${to_bool(context.unread_count) ? context.unread_count : ""}</span
                          >
                          ${to_bool(context.supports_masked_unread)
                              ? html`
                                    <span class="masked_unread_count">
                                        <i class="zulip-icon zulip-icon-masked-unread"></i>
                                    </span>
                                `
                              : ""}
                      </span>
                  `
                : html` <span class="popover-menu-label">${context.name}</span> `}
        </a>
    </li> `;
    return to_html(out);
}
