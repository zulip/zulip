import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_dropdown_widget from "../dropdown_widget.ts";
import render_inbox_list from "./inbox_list.ts";
import render_inbox_no_unreads from "./inbox_no_unreads.ts";

export default function render_inbox_view(context) {
    const out = html`<div id="inbox-main" class="no-select">
        <div class="search_group" id="inbox-filters" role="group">
            ${{__html: render_dropdown_widget({widget_name: "inbox-filter"})}}
            <i class="zulip-icon zulip-icon-search-inbox"></i>
            <input
                type="text"
                id="${context.INBOX_SEARCH_ID}"
                value="${context.search_val}"
                autocomplete="off"
                placeholder="${$t({defaultMessage: "Filter"})}"
            />
            <button id="inbox-clear-search">
                <i class="zulip-icon zulip-icon-close-small"></i>
            </button>
        </div>
        <div id="inbox-empty-with-search" class="inbox-empty-text empty-list-message">
            ${$t({defaultMessage: "No conversations match your filters."})}
        </div>
        ${{__html: render_inbox_no_unreads()}}
        <div id="inbox-list">${{__html: render_inbox_list(context)}}</div>
    </div> `;
    return to_html(out);
}
