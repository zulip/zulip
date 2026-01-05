import {to_array, to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_input_wrapper from "./components/input_wrapper.ts";
import render_empty_list_widget_for_list from "./empty_list_widget_for_list.ts";
import render_left_sidebar_expanded_view_items_list from "./left_sidebar_expanded_view_items_list.ts";
import render_left_sidebar_primary_condensed_view_item from "./left_sidebar_primary_condensed_view_item.ts";

export default function render_left_sidebar(context) {
    const out = html`<div class="left-sidebar" id="left-sidebar" role="navigation">
        <div id="left-sidebar-search" class="zoom-in-hide">
            <div
                class="input-wrapper-for-tooltip tippy-zulip-delayed-tooltip"
                data-tooltip-template-id="filter-left-sidebar-tooltip-template"
            >
                ${{
                    __html: render_input_wrapper(
                        {
                            input_button_icon: "close",
                            icon: "search",
                            custom_classes: "left-sidebar-search-section",
                            input_type: "filter-input",
                        },
                        () => html`
                            <input
                                type="text"
                                class="input-element left-sidebar-search-input home-page-input"
                                autocomplete="off"
                                placeholder="${$t({defaultMessage: "Filter left sidebar"})}"
                            />
                        `,
                    ),
                }}
            </div>
            <span id="add_streams_tooltip" class="add-stream-icon-container hidden-for-spectators">
                <i
                    id="streams_inline_icon"
                    class="add_stream_icon zulip-icon zulip-icon-square-plus"
                    aria-hidden="true"
                ></i>
            </span>
            <span class="sidebar-menu-icon channel-folders-sidebar-menu-icon hidden-for-spectators"
                ><i
                    class="zulip-icon zulip-icon-more-vertical"
                    aria-label="${$t({defaultMessage: "Show channel folders"})}"
                ></i
            ></span>
        </div>
        <ul id="left-sidebar-empty-list-message" class="hidden">
            ${{
                __html: render_empty_list_widget_for_list({
                    empty_list_message: $t({defaultMessage: "No matches."}),
                }),
            }}
        </ul>
        <div id="left-sidebar-navigation-area" class="left-sidebar-navigation-area">
            <div
                id="views-label-container"
                class="showing-expanded-navigation${to_bool(context.is_spectator)
                    ? " remove-pointer-for-spectator"
                    : ""}"
            >
                <i
                    id="toggle-top-left-navigation-area-icon"
                    class="zulip-icon zulip-icon-heading-triangle-right sidebar-heading-icon rotate-icon-down views-tooltip-target hidden-for-spectators"
                    aria-hidden="true"
                    tabindex="0"
                    role="button"
                ></i>
                <h4 class="left-sidebar-title">
                    <span class="views-tooltip-target"
                        >${context.LEFT_SIDEBAR_NAVIGATION_AREA_TITLE}</span
                    >
                </h4>
                <ul id="left-sidebar-navigation-list-condensed" class="filters">
                    ${to_array(context.primary_condensed_views).map(
                        (view) =>
                            html` ${{__html: render_left_sidebar_primary_condensed_view_item(view)}}`,
                    )}
                    <li
                        class="top_left_condensed_unread_marker left-sidebar-navigation-condensed-item"
                    >
                        <span class="unread_count normal-count"></span>
                    </li>
                </ul>
                <div class="left-sidebar-navigation-menu-icon">
                    <i
                        class="zulip-icon zulip-icon-more-vertical"
                        aria-label="${$t({defaultMessage: "Other views"})}"
                    ></i>
                </div>
            </div>
            <ul id="left-sidebar-navigation-list" class="left-sidebar-navigation-list filters">
                ${{
                    __html: render_left_sidebar_expanded_view_items_list({
                        expanded_views: context.expanded_views,
                    }),
                }}
            </ul>
        </div>

        <a id="hide-more-direct-messages" class="trigger-click-on-enter" tabindex="0">
            <span class="hide-more-direct-messages-text">
                ${$t({defaultMessage: "back to channels"})}</span
            >
        </a>
        <div
            id="direct-messages-section-header"
            class="direct-messages-container hidden-for-spectators zoom-out zoom-in-sticky"
        >
            <i
                id="toggle-direct-messages-section-icon"
                class="zulip-icon zulip-icon-heading-triangle-right sidebar-heading-icon rotate-icon-down dm-tooltip-target zoom-in-hide"
                aria-hidden="true"
                tabindex="0"
                role="button"
            ></i>
            <h4 class="left-sidebar-title">
                <span class="dm-tooltip-target">${context.LEFT_SIDEBAR_DIRECT_MESSAGES_TITLE}</span>
            </h4>
            <div class="left-sidebar-controls">
                <a
                    id="show-all-direct-messages"
                    class="tippy-left-sidebar-tooltip-no-label-delay"
                    href="#narrow/is/dm"
                    data-tooltip-template-id="show-all-direct-messages-template"
                >
                    <i
                        class="zulip-icon zulip-icon-all-messages"
                        aria-label="${$t({defaultMessage: "Direct message feed"})}"
                    ></i>
                </a>
                <span
                    id="compose-new-direct-message"
                    class="tippy-left-sidebar-tooltip-no-label-delay auto-hide-left-sidebar-overlay"
                    data-tooltip-template-id="new_direct_message_button_tooltip_template"
                >
                    <i
                        class="left-sidebar-new-direct-message-icon zulip-icon zulip-icon-square-plus"
                        aria-label="${$t({defaultMessage: "New direct message"})}"
                    ></i>
                </span>
            </div>
            <div class="heading-markers-and-unreads">
                <span class="unread_count"></span>
            </div>
            <div
                class="zoom-out-hide direct-messages-search-section left-sidebar-filter-input-container"
            >
                ${{
                    __html: render_input_wrapper(
                        {input_button_icon: "close", icon: "search", input_type: "filter-input"},
                        () => html`
                            <input
                                type="text"
                                class="input-element direct-messages-list-filter home-page-input"
                                autocomplete="off"
                                placeholder="${$t({defaultMessage: "Filter direct messages"})}"
                            />
                        `,
                    ),
                }}
            </div>
        </div>
        <div
            id="left_sidebar_scroll_container"
            class="scrolling_list"
            data-simplebar
            data-simplebar-tab-index="-1"
        >
            <div class="direct-messages-container zoom-out hidden-for-spectators">
                <div id="direct-messages-list"></div>
            </div>

            <div id="streams_list" class="zoom-out">
                <div id="topics_header">
                    <a class="show-all-streams trigger-click-on-enter" tabindex="0"
                        >${$t({defaultMessage: "Back to channels"})}</a
                    >
                    <span class="unread_count quiet-count"></span>
                </div>
                <div id="stream-filters-container">
                    <ul id="stream_filters" class="filters"></ul>
                    ${!to_bool(context.is_guest)
                        ? html` <div id="subscribe-to-more-streams"></div> `
                        : ""}
                    <div
                        id="login-to-more-streams"
                        class="only-visible-for-spectators login_button"
                    >
                        <a class="subscribe-more-link" tabindex="0">
                            <i
                                class="subscribe-more-icon zulip-icon zulip-icon-log-in"
                                aria-hidden="true"
                            ></i>
                            <span class="subscribe-more-label"
                                >${$t({defaultMessage: "LOG IN TO BROWSE MORE"})}</span
                            >
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
