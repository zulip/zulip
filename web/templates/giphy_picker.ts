import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_giphy_picker() {
    const out = html`<div id="giphy_grid_in_popover">
        <div class="arrow"></div>
        <div class="popover-inner">
            <div class="popover-filter-input-wrapper">
                <input
                    type="text"
                    id="giphy-search-query"
                    class="popover-filter-input filter_text_input"
                    autocomplete="off"
                    placeholder="${$t({defaultMessage: "Filter"})}"
                    autofocus
                />
            </div>
            <div class="giphy-scrolling-container" data-simplebar data-simplebar-tab-index="-1">
                ${
                    /* We need a container we can replace
            without removing the simplebar wrappers.
            We replace the `giphy-content` when
            searching for GIFs. */ ""
                }
                <div class="giphy-content"></div>
            </div>
            <div class="popover-footer">
                <img
                    src="../images/giphy/GIPHY_attribution.png"
                    alt="${$t({defaultMessage: "GIPHY attribution"})}"
                />
            </div>
        </div>
    </div> `;
    return to_html(out);
}
