import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import render_status_emoji from "./status_emoji.ts";
import render_user_full_name from "./user_full_name.ts";

export default function render_presence_row(context) {
    const out = html`<li
        data-user-id="${context.user_id}"
        data-name="${context.name}"
        class="user_sidebar_entry ${to_bool(context.user_list_style.WITH_AVATAR)
            ? "with_avatar"
            : ""} ${to_bool(context.has_status_text) ? "with_status" : ""} ${to_bool(
            context.is_current_user,
        )
            ? "user_sidebar_entry_me "
            : ""} narrow-filter ${to_bool(context.faded) ? " user-fade " : ""}"
    >
        <div class="selectable_sidebar_block">
            ${to_bool(context.user_list_style.WITH_STATUS)
                ? html`
                      <span class="${context.user_circle_class} user_circle"></span>
                      <a class="user-presence-link" href="${context.href}">
                          <div class="user-name-and-status-wrapper">
                              <div class="user-name-and-status-emoji">
                                  ${{__html: render_user_full_name(context)}}
                                  ${{__html: render_status_emoji(context.status_emoji_info)}}
                              </div>
                              <span class="status-text">${context.status_text}</span>
                          </div>
                      </a>
                  `
                : to_bool(context.user_list_style.WITH_AVATAR)
                  ? html`
                        <div class="user-profile-picture avatar-preload-background">
                            <img loading="lazy" src="${context.profile_picture}" />
                            <span class="${context.user_circle_class} user_circle"></span>
                        </div>
                        <a class="user-presence-link" href="${context.href}">
                            <div class="user-name-and-status-wrapper">
                                <div class="user-name-and-status-emoji">
                                    ${{__html: render_user_full_name(context)}}
                                    ${{__html: render_status_emoji(context.status_emoji_info)}}
                                </div>
                                <span class="status-text">${context.status_text}</span>
                            </div>
                        </a>
                    `
                  : html`
                        <span class="${context.user_circle_class} user_circle"></span>
                        <a class="user-presence-link" href="${context.href}">
                            <div class="user-name-and-status-emoji">
                                ${{__html: render_user_full_name(context)}}
                                ${{__html: render_status_emoji(context.status_emoji_info)}}
                            </div>
                        </a>
                    `}
            <span class="unread_count ${!to_bool(context.num_unread) ? "hide" : ""}"
                >${to_bool(context.num_unread) ? context.num_unread : ""}</span
            >
        </div>
        ${!to_bool(context.user_list_style.WITH_AVATAR)
            ? html`
                  <span class="sidebar-menu-icon user-list-sidebar-menu-icon"
                      ><i class="zulip-icon zulip-icon-more-vertical" aria-hidden="true"></i
                  ></span>
              `
            : ""}
    </li> `;
    return to_html(out);
}
