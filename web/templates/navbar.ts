import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_navbar(context) {
    const out = html`<div class="header">
        <nav class="header-main" id="top_navbar">
            <div class="column-left">
                <a
                    class="left-sidebar-toggle-button ${to_bool(context.embedded)
                        ? "hide-streamlist-toggle-visibility"
                        : ""}"
                    tabindex="0"
                    role="button"
                >
                    <i class="fa fa-reorder" aria-hidden="true"></i>
                    <span class="left-sidebar-toggle-unreadcount">0</span>
                </a>
                <a href="" class="brand no-style">
                    <img id="realm-navbar-wide-logo" src="" alt="" class="nav-logo no-drag" />
                    <img
                        id="realm-navbar-icon-logo"
                        alt=""
                        src="${context.realm_icon_url}"
                        class="nav-logo no-drag"
                    />
                </a>
            </div>
            <div class="column-middle" id="navbar-middle">
                <div class="column-middle-inner">
                    <div
                        id="streamlist-toggle"
                        class="tippy-zulip-delayed-tooltip ${to_bool(context.embedded)
                            ? "hide-streamlist-toggle-visibility"
                            : ""}"
                        data-tooltip-template-id="show-left-sidebar-tooltip-template"
                    >
                        <a class="left-sidebar-toggle-button" role="button" tabindex="0"
                            ><i class="fa fa-reorder" aria-hidden="true"></i>
                            <span class="left-sidebar-toggle-unreadcount">0</span>
                        </a>
                    </div>
                    <div class="top-navbar-container">
                        <div id="message_view_header" class="notdisplayed"></div>
                        <div id="searchbox">
                            <form id="searchbox_form" class="navbar-search">
                                <div
                                    id="searchbox-input-container"
                                    class="input-append pill-container"
                                >
                                    <i class="search_icon zulip-icon zulip-icon-search"></i>
                                    <div class="search-input-and-pills">
                                        <div
                                            class="search-input input input-block-level home-page-input"
                                            id="search_query"
                                            type="text"
                                            data-placeholder-text="${$t({
                                                defaultMessage: "Search",
                                            })}"
                                            autocomplete="off"
                                            contenteditable="true"
                                        ></div>
                                    </div>
                                    <button
                                        class="search_close_button tippy-zulip-delayed-tooltip"
                                        type="button"
                                        id="search_exit"
                                        aria-label="${$t({defaultMessage: "Exit search"})}"
                                        data-tippy-content="Close"
                                    >
                                        <i
                                            class="zulip-icon zulip-icon-close"
                                            aria-hidden="true"
                                        ></i>
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
            <div class="column-right">
                <div class="spectator_login_buttons only-visible-for-spectators">
                    <a class="login_button"> ${$t({defaultMessage: "Log in"})} </a>
                </div>
                <div id="userlist-toggle" class="hidden-for-spectators">
                    <a id="userlist-toggle-button" role="button" class="header-button" tabindex="0">
                        <i class="zulip-icon zulip-icon-user-list"></i>
                    </a>
                </div>
                <div id="help-menu">
                    <a
                        class="header-button tippy-zulip-delayed-tooltip"
                        tabindex="0"
                        role="button"
                        data-tooltip-template-id="help-menu-tooltip-template"
                    >
                        <i class="zulip-icon zulip-icon-help-bigger" aria-hidden="true"></i>
                    </a>
                </div>
                <div
                    id="gear-menu"
                    class="${to_bool(context.embedded) ? "hide-navbar-buttons-visibility" : ""}"
                >
                    <a
                        id="settings-dropdown"
                        tabindex="0"
                        role="button"
                        class="header-button tippy-zulip-delayed-tooltip"
                        data-tooltip-template-id="gear-menu-tooltip-template"
                    >
                        <i class="zulip-icon zulip-icon-gear" aria-hidden="true"></i>
                    </a>
                </div>
                <div id="personal-menu" class="hidden-for-spectators">
                    <a
                        class="header-button tippy-zulip-delayed-tooltip"
                        tabindex="0"
                        role="button"
                        data-tooltip-template-id="personal-menu-tooltip-template"
                    >
                        <img class="header-button-avatar" src="${context.user_avatar}" />
                    </a>
                </div>
                <div
                    class="spectator_narrow_login_button only-visible-for-spectators"
                    data-tippy-content="${$t({defaultMessage: "Log in"})}"
                    data-tippy-placement="bottom"
                >
                    <a class="header-button login_button">
                        <i class="zulip-icon zulip-icon-log-in"></i>
                    </a>
                </div>
            </div>
        </nav>
    </div> `;
    return to_html(out);
}
