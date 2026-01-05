import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_dropdown_list_container(context) {
    const out = html`<div
        class="dropdown-list-container ${context.widget_name}-dropdown-list-container"
    >
        <div class="dropdown-list-search popover-filter-input-wrapper">
            <input
                class="dropdown-list-search-input popover-filter-input filter_text_input${to_bool(
                    context.hide_search_box,
                )
                    ? " hide"
                    : ""}"
                type="text"
                placeholder="${$t({defaultMessage: "Filter"})}"
                autofocus
            />
        </div>
        <div class="dropdown-list-wrapper" data-simplebar data-simplebar-tab-index="-1">
            <ul class="dropdown-list"></ul>
        </div>
        <div class="no-dropdown-items dropdown-list-item-common-styles">
            ${$t({defaultMessage: "No matching results"})}
        </div>
        ${to_bool(context.sticky_bottom_option)
            ? html`
                  <button class="sticky-bottom-option-button">
                      ${context.sticky_bottom_option}
                  </button>
              `
            : ""}
    </div> `;
    return to_html(out);
}
