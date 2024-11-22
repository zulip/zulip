import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_right_sidebar() {
    const out = html`<div class="right-sidebar" id="right-sidebar" role="navigation">
        <div class="right-sidebar-items">
            <div id="user-list">
                <div id="userlist-header">
                    <div id="userlist-header-search">
                        <input
                            class="user-list-filter home-page-input filter_text_input"
                            type="text"
                            autocomplete="off"
                            placeholder="${$t({defaultMessage: "Filter users"})}"
                        />
                        <button
                            type="button"
                            class="bootstrap-btn hidden"
                            id="clear_search_people_button"
                        >
                            <i class="zulip-icon zulip-icon-close" aria-hidden="true"></i>
                        </button>
                    </div>
                    <span id="buddy-list-menu-icon" class="user-list-sidebar-menu-icon">
                        <i class="zulip-icon zulip-icon-more-vertical" aria-hidden="true"></i>
                    </span>
                </div>
                <div
                    id="buddy_list_wrapper"
                    class="scrolling_list"
                    data-simplebar
                    data-simplebar-tab-index="-1"
                >
                    <div
                        id="buddy-list-participants-container"
                        class="buddy-list-section-container"
                    >
                        <div class="buddy-list-subsection-header"></div>
                        <ul id="buddy-list-participants" class="buddy-list-section"></ul>
                    </div>
                    <div
                        id="buddy-list-users-matching-view-container"
                        class="buddy-list-section-container"
                    >
                        <div class="buddy-list-subsection-header"></div>
                        <ul id="buddy-list-users-matching-view" class="buddy-list-section"></ul>
                    </div>
                    <div id="buddy-list-other-users-container" class="buddy-list-section-container">
                        <div class="buddy-list-subsection-header"></div>
                        <ul id="buddy-list-other-users" class="buddy-list-section"></ul>
                    </div>
                    <div id="buddy_list_wrapper_padding"></div>
                    <div class="invite-user-shortcut">
                        <a class="invite-user-link" role="button">
                            <i class="zulip-icon zulip-icon-user-plus" aria-hidden="true"></i>
                            ${$t({defaultMessage: "Invite users to organization"})}
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
