import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";

export default function render_left_sidebar_expanded_view_item(context) {
    const out = html`<li
        class="top_left_${context.css_class_suffix} top_left_row ${to_bool(
            context.hidden_for_spectators,
        )
            ? "hidden-for-spectators"
            : ""} ${to_bool(context.is_home_view) ? "selected-home-view" : ""}"
    >
        <a
            href="#${context.fragment}"
            class="left-sidebar-navigation-label-container tippy-left-sidebar-tooltip"
            data-tooltip-template-id="${context.tooltip_template_id}"
        >
            <span class="filter-icon">
                <i class="zulip-icon ${context.icon}" aria-hidden="true"></i> </span
            ><span class="left-sidebar-navigation-label">${context.name}</span>
            <span
                class="unread_count ${context.unread_count_type}${!to_bool(context.unread_count)
                    ? " hide"
                    : ""}"
            >
                ${to_bool(context.unread_count) ? html` ${context.unread_count} ` : ""}
            </span>
            ${to_bool(context.supports_masked_unread)
                ? html`
                      <span class="masked_unread_count">
                          <i class="zulip-icon zulip-icon-masked-unread"></i>
                      </span>
                  `
                : ""}
        </a>
        ${to_bool(context.menu_icon_class)
            ? html`
                  <span
                      class="arrow sidebar-menu-icon ${context.menu_icon_class} hidden-for-spectators"
                      ><i
                          class="zulip-icon zulip-icon-more-vertical"
                          aria-label="${context.menu_aria_label}"
                      ></i
                  ></span>
              `
            : ""}
    </li> `;
    return to_html(out);
}
