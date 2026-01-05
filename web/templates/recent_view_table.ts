import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_input_wrapper from "./components/input_wrapper.ts";
import render_recent_view_filters from "./recent_view_filters.ts";

export default function render_recent_view_table(context) {
    const out = html`<div id="recent_view_filter_buttons" role="group">
            <div id="recent_filters_group">${{__html: render_recent_view_filters(context)}}</div>
            ${{
                __html: render_input_wrapper(
                    {
                        input_button_icon: "close",
                        icon: "search",
                        id: "recent-view-search-wrapper",
                        input_type: "filter-input",
                        ...context,
                    },
                    (context1) => html`
                        <input
                            type="text"
                            id="recent_view_search"
                            class="input-element user-list-filter"
                            value="${context1.search_val}"
                            autocomplete="off"
                            placeholder="${$t({defaultMessage: "Filter topics"})}"
                        />
                    `,
                ),
            }}
        </div>
        <div class="table_fix_head">
            <div class="recent-view-container">
                <table class="table table-responsive">
                    <thead id="recent-view-table-headers">
                        <tr>
                            <th class="recent-view-stream-header" data-sort="stream_sort">
                                ${$t({defaultMessage: "Channel"})}
                                <i
                                    class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                                ></i>
                            </th>
                            <th class="recent-view-topic-header" data-sort="topic_sort">
                                ${$t({defaultMessage: "Topic"})}
                                <i
                                    class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                                ></i>
                            </th>
                            <th
                                data-sort="unread_sort"
                                data-tippy-content="${$t({
                                    defaultMessage: "Sort by unread message count",
                                })}"
                                class="recent-view-unread-header unread_sort tippy-zulip-delayed-tooltip hidden-for-spectators"
                            >
                                <i class="zulip-icon zulip-icon-unread"></i>
                                <i
                                    class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                                ></i>
                            </th>
                            <th class="recent-view-participants-header participants_header">
                                ${$t({defaultMessage: "Participants"})}
                            </th>
                            <th
                                data-sort="numeric"
                                data-sort-prop="last_msg_id"
                                class="recent-view-last-msg-time-header last_msg_time_header active descend"
                            >
                                ${$t({defaultMessage: "Time"})}
                                <i
                                    class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                                ></i>
                            </th>
                        </tr>
                    </thead>
                </table>
            </div>
        </div> `;
    return to_html(out);
}
