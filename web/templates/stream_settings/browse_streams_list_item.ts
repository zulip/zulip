import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";
import {postprocess_content} from "../../src/postprocess_content.ts";
import render_inline_decorated_channel_name from "../inline_decorated_channel_name.ts";
import render_subscriber_count from "./subscriber_count.ts";
import render_subscription_setting_icon from "./subscription_setting_icon.ts";

export default function render_browse_streams_list_item(context) {
    const out = /* Client-side Handlebars template for rendering subscriptions. */ html`<div
        class="stream-row"
        data-stream-id="${context.stream_id}"
        data-stream-name="${context.name}"
    >
        ${to_bool(context.subscribed)
            ? html`
                  <div class="check checked sub_unsub_button">
                      <div
                          class="tippy-zulip-tooltip"
                          data-tooltip-template-id="unsubscribe-from-${context.stream_id}-stream-tooltip-template"
                      >
                          <template
                              id="unsubscribe-from-${context.stream_id}-stream-tooltip-template"
                          >
                              <span>
                                  ${$html_t(
                                      {defaultMessage: "Unsubscribe from <z-stream></z-stream>"},
                                      {
                                          ["z-stream"]: () => ({
                                              __html: render_inline_decorated_channel_name({
                                                  stream: context,
                                              }),
                                          }),
                                      },
                                  )}
                              </span>
                          </template>

                          <i class="zulip-icon zulip-icon-subscriber-check sub-unsub-icon"></i>
                      </div>
                      <div class="sub_unsub_status"></div>
                  </div>
              `
            : html`
                  <div
                      class="check sub_unsub_button ${!to_bool(
                          context.should_display_subscription_button,
                      )
                          ? "disabled"
                          : ""}"
                  >
                      <div
                          class="tippy-zulip-tooltip"
                          data-tooltip-template-id="${to_bool(
                              context.should_display_subscription_button,
                          )
                              ? html`subscribe-to-${context.stream_id}-stream-tooltip-template`
                              : html`cannot-subscribe-to-${context.stream_id}-stream-tooltip-template`}"
                      >
                          <template id="subscribe-to-${context.stream_id}-stream-tooltip-template">
                              <span>
                                  ${$html_t(
                                      {defaultMessage: "Subscribe to <z-stream></z-stream>"},
                                      {
                                          ["z-stream"]: () => ({
                                              __html: render_inline_decorated_channel_name({
                                                  stream: context,
                                              }),
                                          }),
                                      },
                                  )}
                              </span>
                          </template>

                          <template
                              id="cannot-subscribe-to-${context.stream_id}-stream-tooltip-template"
                          >
                              <span>
                                  ${$html_t(
                                      {defaultMessage: "Cannot subscribe to <z-stream></z-stream>"},
                                      {
                                          ["z-stream"]: () => ({
                                              __html: render_inline_decorated_channel_name({
                                                  stream: context,
                                              }),
                                          }),
                                      },
                                  )}
                              </span>
                          </template>

                          <i class="zulip-icon zulip-icon-subscriber-plus sub-unsub-icon"></i>
                      </div>
                      <div class="sub_unsub_status"></div>
                  </div>
              `}
        ${{__html: render_subscription_setting_icon(context)}}
        <div class="sub-info-box">
            <div class="top-bar">
                <div class="stream-name">${context.name}</div>
                <div
                    class="subscriber-count tippy-zulip-tooltip"
                    data-tippy-content="${$t({defaultMessage: "Subscriber count"})}"
                >
                    ${{__html: render_subscriber_count(context)}}
                </div>
            </div>
            <div class="bottom-bar">
                <div
                    class="description rendered_markdown"
                    data-no-description="${$t({defaultMessage: "No description."})}"
                >
                    ${{__html: postprocess_content(context.rendered_description)}}
                </div>
                ${to_bool(context.is_old_stream)
                    ? html`
                          <div
                              class="stream-message-count tippy-zulip-tooltip"
                              data-tippy-content="${$t({
                                  defaultMessage: "Estimated messages per week",
                              })}"
                          >
                              <i class="fa fa-bar-chart"></i>
                              <span class="stream-message-count-text"
                                  >${context.stream_weekly_traffic}</span
                              >
                          </div>
                      `
                    : html`
                          <div
                              class="stream-message-count tippy-zulip-tooltip"
                              data-tippy-content="${$t({
                                  defaultMessage: "Channel created recently",
                              })}"
                          >
                              <span class="stream-message-count-text"
                                  >${$t({defaultMessage: "New"})}</span
                              >
                          </div>
                      `}
            </div>
        </div>
    </div> `;
    return to_html(out);
}
