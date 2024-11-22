import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_inbox_row from "./inbox_row.ts";
import render_inbox_stream_container from "./inbox_stream_container.ts";

export default function render_inbox_list(context) {
    const out = html`<div
            id="inbox-dm-header"
            tabindex="0"
            class="inbox-header ${!to_bool(context.has_dms_post_filter) ? "hidden_by_filters" : ""}"
        >
            <div class="inbox-focus-border">
                <div class="inbox-left-part-wrapper">
                    <div class="collapsible-button">
                        <i
                            class="zulip-icon zulip-icon-arrow-down toggle-inbox-header-icon ${to_bool(
                                context.is_dms_collapsed,
                            )
                                ? "icon-collapsed-state"
                                : ""}"
                        ></i>
                    </div>
                    <div class="inbox-left-part">
                        <div tabindex="0" class="inbox-header-name">
                            <div class="inbox-header-name-focus-border">
                                <i class="zulip-icon zulip-icon-user"></i>
                                <a tabindex="-1" role="button" href="/#narrow/is/private"
                                    >${$t({defaultMessage: "Direct messages"})}</a
                                >
                            </div>
                        </div>
                        <div class="unread-count-focus-outline" tabindex="0">
                            <span
                                class="unread_count tippy-zulip-tooltip on_hover_all_dms_read"
                                data-tippy-content="${$t({defaultMessage: "Mark as read"})}"
                                aria-label="${$t({defaultMessage: "Mark as read"})}"
                                >${context.unread_dms_count}</span
                            >
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div id="inbox-direct-messages-container">
            ${to_array(context.dms_dict).map((dm) => html` ${{__html: render_inbox_row(dm[1])}}`)}
        </div>

        <div id="inbox-streams-container">
            ${{__html: render_inbox_stream_container(context)}}
        </div> `;
    return to_html(out);
}
