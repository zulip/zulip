import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_add_subscribers_form from "./add_subscribers_form.ts";
import render_stream_members_table from "./stream_members_table.ts";

export default function render_stream_members(context) {
    const out = to_bool(context.render_subscribers)
        ? html`<div
              class="subscriber_list_settings_container"
              ${!to_bool(context.can_access_subscribers) ? html`style="display: none"` : ""}
          >
              <h4 class="stream_setting_subsection_title">
                  ${$t({defaultMessage: "Add subscribers"})}
              </h4>
              <div class="subscriber_list_settings">
                  <div class="subscriber_list_add float-left">
                      ${{__html: render_add_subscribers_form(context)}}
                      <div class="stream_subscription_request_result"></div>
                  </div>
                  <div class="clear-float"></div>
              </div>
              <div>
                  <h4 class="inline-block stream_setting_subsection_title">
                      ${$t({defaultMessage: "Subscribers"})}
                  </h4>
                  <span class="subscriber-search float-right">
                      <input
                          type="text"
                          class="search filter_text_input"
                          placeholder="${$t({defaultMessage: "Filter subscribers"})}"
                      />
                  </span>
              </div>
              <div class="subscriber-list-box">
                  ${{__html: render_stream_members_table(context)}}
              </div>
          </div> `
        : "";
    return to_html(out);
}
