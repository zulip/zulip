import {html, to_html} from "../../shared/src/html.ts";
import {to_array} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_playground_links_popover(context) {
    const out = html`<div
        class="popover-menu playground-links-popover"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <ul role="menu" class="popover-menu-list">
            ${to_array(context.playground_info).map(
                (playground) => html`
                    <li role="none" class="link-item popover-menu-list-item">
                        <a
                            href="${playground.playground_url}"
                            target="_blank"
                            rel="noopener noreferrer"
                            role="menuitem"
                            class="popover_playground_link popover-menu-link"
                            tabindex="0"
                        >
                            <span class="popover-menu-label"
                                >${$t(
                                    {defaultMessage: "View in {name}"},
                                    {name: playground.name},
                                )}</span
                            >
                        </a>
                    </li>
                `,
            )}
        </ul>
    </div> `;
    return to_html(out);
}
