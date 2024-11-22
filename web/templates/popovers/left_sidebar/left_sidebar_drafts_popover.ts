import {html, to_html} from "../../../shared/src/html.ts";
import {$t} from "../../../src/i18n.ts";

export default function render_left_sidebar_drafts_popover() {
    const out = html`<div class="popover-menu" data-simplebar data-simplebar-tab-index="-1">
        <ul role="menu" class="popover-menu-list">
            <li role="none" class="link-item popover-menu-list-item">
                <a
                    role="menuitem"
                    id="delete_all_drafts_sidebar"
                    class="popover-menu-link"
                    tabindex="0"
                >
                    <i class="popover-menu-icon zulip-icon zulip-icon-trash" aria-hidden="true"></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Delete all drafts"})}</span
                    >
                </a>
            </li>
        </ul>
    </div> `;
    return to_html(out);
}
