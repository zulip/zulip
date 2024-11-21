import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_left_sidebar(context) {
    const out = html`<div class="left-sidebar" id="left-sidebar" role="navigation">
        <div id="left-sidebar-navigation-area" class="left-sidebar-navigation-area">
            <div
                id="views-label-container"
                class="showing-expanded-navigation ${to_bool(context.is_spectator)
                    ? "remove-pointer-for-spectator"
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
                    <span class="views-tooltip-target">${$t({defaultMessage: "VIEWS"})}</span>
                </h4>
                <ul id="left-sidebar-navigation-list-condensed" class="filters">
                    <li
                        class="top_left_inbox left-sidebar-navigation-condensed-item ${to_bool(
                            context.is_inbox_home_view,
                        )
                            ? "selected-home-view"
                            : ""}"
                    >
                        <a
                            href="#inbox"
                            class="tippy-views-tooltip left-sidebar-navigation-icon-container"
                            data-tooltip-template-id="inbox-tooltip-template"
                        >
                            <span class="filter-icon">
                                <i class="zulip-icon zulip-icon-inbox" aria-hidden="true"></i>
                            </span>
                            <span class="unread_count"></span>
                        </a>
                    </li>
                    <li
                        class="top_left_recent_view left-sidebar-navigation-condensed-item ${to_bool(
                            context.is_recent_view_home_view,
                        )
                            ? "selected-home-view"
                            : ""}"
                    >
                        <a
                            href="#recent"
                            class="tippy-views-tooltip left-sidebar-navigation-icon-container"
                            data-tooltip-template-id="recent-conversations-tooltip-template"
                        >
                            <span class="filter-icon">
                                <i class="zulip-icon zulip-icon-recent" aria-hidden="true"></i>
                            </span>
                            <span class="unread_count"></span>
                        </a>
                    </li>
                    <li
                        class="top_left_all_messages left-sidebar-navigation-condensed-item ${to_bool(
                            context.is_all_messages_home_view,
                        )
                            ? "selected-home-view"
                            : ""}"
                    >
                        <a
                            href="#feed"
                            class="home-link tippy-views-tooltip left-sidebar-navigation-icon-container"
                            data-tooltip-template-id="all-message-tooltip-template"
                        >
                            <span class="filter-icon">
                                <i
                                    class="zulip-icon zulip-icon-all-messages"
                                    aria-hidden="true"
                                ></i>
                            </span>
                            <span class="unread_count"></span>
                        </a>
                    </li>
                    <li class="top_left_mentions left-sidebar-navigation-condensed-item">
                        <a
                            href="#narrow/is/mentioned"
                            class="tippy-left-sidebar-tooltip left-sidebar-navigation-icon-container"
                            data-tooltip-template-id="mentions-tooltip-template"
                        >
                            <span class="filter-icon">
                                <i class="zulip-icon zulip-icon-at-sign" aria-hidden="true"></i>
                            </span>
                            <span class="unread_count"></span>
                        </a>
                    </li>
                    <li class="top_left_starred_messages left-sidebar-navigation-condensed-item">
                        <a
                            href="#narrow/is/starred"
                            class="tippy-left-sidebar-tooltip left-sidebar-navigation-icon-container"
                            data-tooltip-template-id="starred-tooltip-template"
                        >
                            <span class="filter-icon">
                                <i class="zulip-icon zulip-icon-star" aria-hidden="true"></i>
                            </span>
                            <span class="unread_count quiet-count"></span>
                        </a>
                    </li>
                </ul>
                <div class="left-sidebar-navigation-menu-icon">
                    <i class="zulip-icon zulip-icon-more-vertical"></i>
                </div>
            </div>
            <ul id="left-sidebar-navigation-list" class="left-sidebar-navigation-list filters">
                <li
                    class="top_left_inbox top_left_row hidden-for-spectators ${to_bool(
                        context.is_inbox_home_view,
                    )
                        ? "selected-home-view"
                        : ""}"
                >
                    <a
                        href="#inbox"
                        class="left-sidebar-navigation-label-container tippy-views-tooltip"
                        data-tooltip-template-id="inbox-tooltip-template"
                    >
                        <span class="filter-icon">
                            <i class="zulip-icon zulip-icon-inbox" aria-hidden="true"></i> </span
                        ><span class="left-sidebar-navigation-label"
                            >${$t({defaultMessage: "Inbox"})}</span
                        >
                        <span class="unread_count"></span>
                    </a>
                    <span
                        class="arrow sidebar-menu-icon inbox-sidebar-menu-icon hidden-for-spectators"
                        ><i class="zulip-icon zulip-icon-more-vertical" aria-hidden="true"></i
                    ></span>
                </li>
                <li
                    class="top_left_recent_view top_left_row ${to_bool(
                        context.is_recent_view_home_view,
                    )
                        ? "selected-home-view"
                        : ""}"
                >
                    <a
                        href="#recent"
                        class="left-sidebar-navigation-label-container tippy-views-tooltip"
                        data-tooltip-template-id="recent-conversations-tooltip-template"
                    >
                        <span class="filter-icon">
                            <i class="zulip-icon zulip-icon-recent" aria-hidden="true"></i> </span
                        ><span class="left-sidebar-navigation-label"
                            >${$t({defaultMessage: "Recent conversations"})}</span
                        >
                        <span class="unread_count"></span>
                    </a>
                    <span
                        class="arrow sidebar-menu-icon recent-view-sidebar-menu-icon hidden-for-spectators"
                    >
                        <i class="zulip-icon zulip-icon-more-vertical" aria-hidden="true"></i>
                    </span>
                </li>
                <li
                    class="top_left_all_messages top_left_row ${to_bool(
                        context.is_all_messages_home_view,
                    )
                        ? "selected-home-view"
                        : ""}"
                >
                    <a
                        href="#feed"
                        class="home-link left-sidebar-navigation-label-container tippy-views-tooltip"
                        data-tooltip-template-id="all-message-tooltip-template"
                    >
                        <span class="filter-icon">
                            <i
                                class="zulip-icon zulip-icon-all-messages"
                                aria-hidden="true"
                            ></i> </span
                        ><span class="left-sidebar-navigation-label"
                            >${$t({defaultMessage: "Combined feed"})}</span
                        >
                        <span class="unread_count"></span>
                    </a>
                    <span
                        class="arrow sidebar-menu-icon all-messages-sidebar-menu-icon hidden-for-spectators"
                    >
                        <i class="zulip-icon zulip-icon-more-vertical" aria-hidden="true"></i>
                    </span>
                </li>
                <li class="top_left_mentions top_left_row hidden-for-spectators">
                    <a class="left-sidebar-navigation-label-container" href="#narrow/is/mentioned">
                        <span class="filter-icon">
                            <i class="zulip-icon zulip-icon-at-sign" aria-hidden="true"></i> </span
                        ><span class="left-sidebar-navigation-label"
                            >${$t({defaultMessage: "Mentions"})}</span
                        >
                        <span class="unread_count"></span>
                    </a>
                </li>
                <li class="top_left_my_reactions top_left_row hidden-for-spectators">
                    <a
                        class="left-sidebar-navigation-label-container tippy-views-tooltip"
                        href="#narrow/has/reaction/sender/me"
                        data-tooltip-template-id="my-reactions-tooltip-template"
                    >
                        <span class="filter-icon">
                            <i class="zulip-icon zulip-icon-smile" aria-hidden="true"></i> </span
                        ><span class="left-sidebar-navigation-label"
                            >${$t({defaultMessage: "Reactions"})}</span
                        >
                        <span class="unread_count"></span>
                    </a>
                </li>
                <li class="top_left_starred_messages top_left_row hidden-for-spectators">
                    <a
                        class="left-sidebar-navigation-label-container tippy-views-tooltip"
                        href="#narrow/is/starred"
                        data-tooltip-template-id="starred-message-tooltip-template"
                    >
                        <span class="filter-icon">
                            <i class="zulip-icon zulip-icon-star" aria-hidden="true"></i> </span
                        ><span class="left-sidebar-navigation-label"
                            >${$t({defaultMessage: "Starred messages"})}</span
                        >
                        <span class="unread_count quiet-count"></span>
                        <span class="masked_unread_count">
                            <i class="zulip-icon zulip-icon-masked-unread"></i>
                        </span>
                    </a>
                    <span class="arrow sidebar-menu-icon starred-messages-sidebar-menu-icon"
                        ><i class="zulip-icon zulip-icon-more-vertical" aria-hidden="true"></i
                    ></span>
                </li>
                <li class="top_left_drafts top_left_row hidden-for-spectators">
                    <a
                        href="#drafts"
                        class="left-sidebar-navigation-label-container tippy-views-tooltip"
                        data-tooltip-template-id="drafts-tooltip-template"
                    >
                        <span class="filter-icon">
                            <i class="zulip-icon zulip-icon-drafts" aria-hidden="true"></i> </span
                        ><span class="left-sidebar-navigation-label"
                            >${$t({defaultMessage: "Drafts"})}</span
                        >
                        <span class="unread_count quiet-count"></span>
                    </a>
                    <span class="arrow sidebar-menu-icon drafts-sidebar-menu-icon"
                        ><i class="zulip-icon zulip-icon-more-vertical" aria-hidden="true"></i
                    ></span>
                </li>
                <li class="top_left_scheduled_messages top_left_row hidden-for-spectators">
                    <a class="left-sidebar-navigation-label-container" href="#scheduled">
                        <span class="filter-icon">
                            <i
                                class="zulip-icon zulip-icon-calendar-days"
                                aria-hidden="true"
                            ></i> </span
                        ><span class="left-sidebar-navigation-label"
                            >${$t({defaultMessage: "Scheduled messages"})}</span
                        >
                        <span class="unread_count quiet-count"></span>
                    </a>
                </li>
            </ul>
        </div>

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
                <span class="dm-tooltip-target">${$t({defaultMessage: "DIRECT MESSAGES"})}</span>
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
                    class="tippy-left-sidebar-tooltip-no-label-delay"
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
            <a class="zoom-out-hide" id="hide-more-direct-messages">
                <span class="hide-more-direct-messages-text">
                    ${$t({defaultMessage: "back to channels"})}</span
                >
            </a>
            <div class="zoom-out-hide direct-messages-search-section">
                <input
                    class="direct-messages-list-filter filter_text_input home-page-input"
                    type="text"
                    autocomplete="off"
                    placeholder="${$t({defaultMessage: "Filter direct messages"})}"
                />
                <button
                    type="button"
                    class="bootstrap-btn clear_search_button"
                    id="clear-direct-messages-search-button"
                >
                    <i class="fa fa-remove" aria-hidden="true"></i>
                </button>
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
                <div
                    id="streams_header"
                    class="zoom-in-hide ${to_bool(context.hide_unread_counts)
                        ? "hide_unread_counts"
                        : ""}"
                >
                    <h4 class="left-sidebar-title">
                        <span
                            class="streams-tooltip-target"
                            data-tooltip-template-id="filter-streams-tooltip-template"
                            >${$t({defaultMessage: "CHANNELS"})}</span
                        >
                    </h4>
                    <div class="left-sidebar-controls">
                        <i
                            id="filter_streams_tooltip"
                            class="streams_filter_icon zulip-icon zulip-icon-search"
                            aria-hidden="true"
                            data-tooltip-template-id="filter-streams-tooltip-template"
                        ></i>
                        <span
                            id="add_streams_tooltip"
                            class="hidden-for-spectators"
                            data-tippy-content="${$t({defaultMessage: "Add channels"})}"
                        >
                            <i
                                id="streams_inline_icon"
                                class="zulip-icon zulip-icon-square-plus"
                                aria-hidden="true"
                            ></i>
                        </span>
                    </div>
                    <div class="heading-markers-and-unreads">
                        <span class="unread_count"></span>
                        <span class="masked_unread_count">
                            <i class="zulip-icon zulip-icon-masked-unread"></i>
                        </span>
                    </div>

                    <div class="notdisplayed stream_search_section">
                        <input
                            class="stream-list-filter home-page-input filter_text_input"
                            type="text"
                            autocomplete="off"
                            placeholder="${$t({defaultMessage: "Filter channels"})}"
                        />
                        <button
                            type="button"
                            class="bootstrap-btn clear_search_button"
                            id="clear_search_stream_button"
                        >
                            <i class="fa fa-remove" aria-hidden="true"></i>
                        </button>
                    </div>
                </div>
                <div id="topics_header">
                    <a class="show-all-streams" tabindex="0"
                        >${$t({defaultMessage: "Back to channels"})}</a
                    >
                    <span class="unread_count"></span>
                </div>
                <div id="stream-filters-container">
                    <ul id="stream_filters" class="filters"></ul>
                    ${!to_bool(context.is_guest)
                        ? html` <div id="subscribe-to-more-streams"></div> `
                        : ""}
                    <div class="only-visible-for-spectators">
                        <div id="login-link-container" class="login_button">
                            <i class="zulip-icon zulip-icon-log-in" aria-hidden="true"></i
                            ><a class="login-text">
                                ${$t({defaultMessage: "Log in to browse more channels"})}
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
