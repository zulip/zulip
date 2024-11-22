import {html, to_html} from "../../../shared/src/html.ts";
import {to_array, to_bool} from "../../../src/hbs_compat.ts";
import {$t} from "../../../src/i18n.ts";

export default function render_emoji_popover(context) {
    const out = html`<div
        class="emoji-picker-popover"
        data-emoji-destination="${to_bool(context.message_id)
            ? "reaction"
            : to_bool(context.is_status_emoji_popover)
              ? "status"
              : "composition"}"
    >
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
                data-message-id="${context.message_id}"
            ></div>
            <div
                class="emoji-search-results-container"
                data-simplebar
                data-simplebar-tab-index="-1"
                data-simplebar-auto-hide="false"
                data-message-id="${context.message_id}"
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
