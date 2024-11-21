import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_input_wrapper from "../components/input_wrapper.ts";
import render_dropdown_widget from "../dropdown_widget.ts";
import render_view_bottom_loading_indicator from "../view_bottom_loading_indicator.ts";
import render_inbox_list from "./inbox_list.ts";
import render_inbox_no_unreads from "./inbox_no_unreads.ts";

export default function render_inbox_view(context) {
    const out = html`<div id="inbox-main">
        ${to_bool(context.unknown_channel)
            ? html`
                  <div id="inbox-unknown-channel-view" class="empty-list-message">
                      ${$t({
                          defaultMessage:
                              "This channel doesn't exist, or you are not allowed to view it.",
                      })}
                  </div>
              `
            : html`
                  <div class="search_group" id="inbox-filters" role="group">
                      ${{__html: render_dropdown_widget({widget_name: "inbox-filter"})}}${{
                          __html: render_input_wrapper(
                              {
                                  input_button_icon: "close",
                                  icon: "search",
                                  custom_classes: "inbox-search-wrapper",
                                  input_type: "filter-input",
                                  ...context,
                              },
                              (context1) => html`
                                  <input
                                      type="text"
                                      id="${context1.INBOX_SEARCH_ID}"
                                      class="input-element"
                                      value="${context1.search_val}"
                                      autocomplete="off"
                                      placeholder="${$t({defaultMessage: "Filter"})}"
                                  />
                              `,
                          ),
                      }}${to_bool(context.show_channel_folder_toggle)
                          ? html`
                                <span
                                    class="sidebar-menu-icon channel-folders-inbox-menu-icon hidden-for-spectators"
                                    ><i
                                        class="zulip-icon zulip-icon-more-vertical"
                                        aria-label="${$t({defaultMessage: "Show channel folders"})}"
                                    ></i
                                ></span>
                            `
                          : ""}
                  </div>
                  <div id="inbox-empty-with-search" class="inbox-empty-text empty-list-message">
                      ${$t({defaultMessage: "No conversations match your filters."})}
                  </div>
                  <div
                      id="inbox-empty-channel-view-with-search"
                      class="inbox-empty-text empty-list-message"
                  >
                      ${$t({defaultMessage: "No topics match your filters."})}
                  </div>
                  <div
                      id="inbox-empty-channel-view-without-search"
                      class="inbox-empty-text empty-list-message"
                  >
                      ${$t({defaultMessage: "There are no topics in this view."})}
                  </div>
                  ${to_bool(context.normal_view)
                      ? html` ${{__html: render_inbox_no_unreads()}}`
                      : ""}
                  <div id="inbox-list">
                      ${to_bool(context.normal_view)
                          ? html` ${{__html: render_inbox_list(context)}}`
                          : ""}
                  </div>
                  <div id="inbox-collapsed-note">
                      <div class="inbox-collapsed-note-and-button-wrapper">
                          <span class="inbox-collapsed-note-span">
                              ${$t({
                                  defaultMessage:
                                      "All unread conversations are hidden. Click on a section, folder, or channel to expand it.",
                              })}
                          </span>
                          <button
                              id="inbox-expand-all-button"
                              class="action-button action-button-quiet-neutral"
                              tabindex="0"
                          >
                              <span class="action-button-label"
                                  >${$t({defaultMessage: "Show all"})}</span
                              >
                          </button>
                      </div>
                  </div>
                  <div id="inbox-loading-indicator">
                      ${!to_bool(context.normal_view)
                          ? html` ${{__html: render_view_bottom_loading_indicator()}}`
                          : ""}
                  </div>
              `}
    </div> `;
    return to_html(out);
}
