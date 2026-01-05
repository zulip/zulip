import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";

export default function render_left_sidebar_primary_condensed_view_item(context) {
    const out = html`<li
        class="top_left_${context.css_class_suffix} left-sidebar-navigation-condensed-item${to_bool(
            context.is_home_view,
        )
            ? " selected-home-view"
            : ""}"
    >
        <a
            href="#${context.fragment}"
            class="tippy-left-sidebar-tooltip left-sidebar-navigation-icon-container"
            data-tooltip-template-id="${context.tooltip_template_id}"
        >
            <span class="filter-icon">
                <i class="zulip-icon ${context.icon}" aria-hidden="true"></i>
            </span>
            <span class="unread_count ${context.unread_count_type}"></span>
        </a>
    </li> `;
    return to_html(out);
}
