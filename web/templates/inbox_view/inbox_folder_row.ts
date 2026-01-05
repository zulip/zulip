import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_inbox_folder_row(context) {
    const out = /* col-index `0` is COLUMNS.FULL_ROW */ html`<div
        id="${context.header_id}"
        tabindex="0"
        class="inbox-header inbox-folder ${!to_bool(context.is_header_visible)
            ? "hidden_by_filters"
            : ""} ${to_bool(context.is_collapsed) ? "inbox-collapsed-state" : ""}"
        data-col-index="0"
    >
        <div class="inbox-focus-border">
            <div class="inbox-left-part-wrapper">
                <div class="inbox-left-part">
                    <div class="inbox-header-name">
                        <span class="inbox-header-name-text">
                            ${to_bool(context.is_dm_header)
                                ? html` ${$t({defaultMessage: "DIRECT MESSAGES"})} `
                                : html` ${context.name} `}
                        </span>
                    </div>
                    <div class="collapsible-button">
                        <i class="folder-row-chevron zulip-icon zulip-icon-chevron-down"></i>
                    </div>
                    <span
                        class="unread_mention_info tippy-zulip-tooltip
                  ${!to_bool(context.has_unread_mention) ? "hidden" : ""}"
                        data-tippy-content="${$t({defaultMessage: "You have unread mentions"})}"
                        >@</span
                    >
                    <div class="unread-count-focus-outline">
                        <span class="unread_count">${context.unread_count}</span>
                    </div>
                </div>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
