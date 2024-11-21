import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_gif_picker_ui(context) {
    const out = html`<div class="gif-grid-in-popover">
        <div class="arrow"></div>
        <div class="popover-inner">
            <div class="popover-filter-input-wrapper">
                ${to_bool(context.is_giphy)
                    ? html`
                          <input
                              type="text"
                              id="gif-search-query"
                              class="popover-filter-input filter_text_input"
                              autocomplete="off"
                              placeholder="${$t({defaultMessage: "Filter"})}"
                              autofocus
                          />
                      `
                    : html`
                          <input
                              type="text"
                              id="gif-search-query"
                              class="popover-filter-input filter_text_input"
                              autocomplete="off"
                              placeholder="${$t({defaultMessage: "Search Tenor"})}"
                              autofocus
                          />
                      `}
                <button
                    type="button"
                    class="clear-search-button"
                    id="gif-search-clear"
                    tabindex="-1"
                >
                    <i class="zulip-icon zulip-icon-close" aria-hidden="true"></i>
                </button>
            </div>
            <div class="gif-scrolling-container" data-simplebar data-simplebar-tab-index="-1">
                ${
                    /* We need a container we can replace
            without removing the simplebar wrappers.
            We replace the `giphy-content`/`tenor-content` when
            searching for GIFs. */ ""
                }${to_bool(context.is_giphy)
                    ? html` <div class="giphy-content"></div> `
                    : html` <div class="tenor-content"></div> `}
            </div>
            ${
                /* We are required to include the
        "Powered By GIPHY" banner, which isn't mandatory
        for Tenor. So we avoid including one for Tenor
        to save space. */ ""
            }${to_bool(context.is_giphy)
                ? html`
                      <div class="popover-footer">
                          <img
                              src="../images/giphy/GIPHY_attribution.png"
                              alt="${$t({defaultMessage: "GIPHY attribution"})}"
                          />
                      </div>
                  `
                : ""}
        </div>
    </div> `;
    return to_html(out);
}
