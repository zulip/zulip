import {to_array} from "../../../src/hbs_compat.ts";
import {html, to_html} from "../../../src/html.ts";
import {$t} from "../../../src/i18n.ts";

export default function render_emoji_popover(context) {
    const out = html`<div class="emoji-picker-popover">
        <div class="emoji-popover">
            <div class="popover-filter-input-wrapper">
                <input
                    id="emoji-popover-filter"
                    class="popover-filter-input filter_text_input"
                    type="text"
                    autocomplete="off"
                    placeholder="${$t({defaultMessage: "Filter"})}"
                    autofocus
                />
            </div>
            <div class="emoji-popover-category-tabs">
                ${to_array(context.emoji_categories).map(
                    (category, category_index) => html`
                        <span
                            class="emoji-popover-tab-item ${category_index === 0 ? " active " : ""}"
                            data-tab-name="${category.name}"
                            title="${category.name}"
                            ><i class="fa ${category.icon}"></i
                        ></span>
                    `,
                )}
            </div>
            <div
                class="emoji-popover-emoji-map"
                data-simplebar
                data-simplebar-tab-index="-1"
                data-simplebar-auto-hide="false"
            ></div>
            <div
                class="emoji-search-results-container"
                data-simplebar
                data-simplebar-tab-index="-1"
                data-simplebar-auto-hide="false"
            >
                <div class="emoji-popover-results-heading">
                    ${$t({defaultMessage: "Search results"})}
                </div>
                <div class="emoji-search-results"></div>
            </div>
        </div>
        <div class="emoji-showcase-container"></div>
    </div> `;
    return to_html(out);
}
