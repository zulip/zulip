import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t, $t} from "../../src/i18n.ts";
import {postprocess_content} from "../../src/postprocess_content.ts";
import render_inline_decorated_stream_name from "../inline_decorated_stream_name.ts";
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
                  <div
                      class="check checked sub_unsub_button tippy-zulip-tooltip"
                      data-tooltip-template-id="unsubscribe-from-${context.name}-stream-tooltip-template"
                  >
                      <template id="unsubscribe-from-${context.name}-stream-tooltip-template">
                          <span>
                              ${$html_t(
                                  {defaultMessage: "Unsubscribe from <z-stream></z-stream>"},
                                  {
                                      ["z-stream"]: () => ({
                                          __html: render_inline_decorated_stream_name({
                                              stream: context,
                                          }),
                                      }),
                                  },
                              )}
                          </span>
                      </template>

                      <svg
                          version="1.1"
                          xmlns="http://www.w3.org/2000/svg"
                          xmlns:xlink="http://www.w3.org/1999/xlink"
                          x="0px"
                          y="0px"
                          width="100%"
                          height="100%"
                          viewBox="0 0 512 512"
                          style="enable-background:new 0 0 512 512;"
                          xml:space="preserve"
                      >
                          <path
                              d="M448,71.9c-17.3-13.4-41.5-9.3-54.1,9.1L214,344.2l-99.1-107.3c-14.6-16.6-39.1-17.4-54.7-1.8 c-15.6,15.5-16.4,41.6-1.7,58.1c0,0,120.4,133.6,137.7,147c17.3,13.4,41.5,9.3,54.1-9.1l206.3-301.7 C469.2,110.9,465.3,85.2,448,71.9z"
                          />
                      </svg>
                      <div class="sub_unsub_status"></div>
                  </div>
              `
            : html`
                  <div
                      class="check sub_unsub_button ${!to_bool(
                          context.should_display_subscription_button,
                      )
                          ? "disabled"
                          : ""} tippy-zulip-tooltip"
                      data-tooltip-template-id="${to_bool(
                          context.should_display_subscription_button,
                      )
                          ? html`subscribe-to-${context.name}-stream-tooltip-template`
                          : html`cannot-subscribe-to-${context.name}-stream-tooltip-template`}"
                  >
                      <template id="subscribe-to-${context.name}-stream-tooltip-template">
                          <span>
                              ${$html_t(
                                  {defaultMessage: "Subscribe to <z-stream></z-stream>"},
                                  {
                                      ["z-stream"]: () => ({
                                          __html: render_inline_decorated_stream_name({
                                              stream: context,
                                          }),
                                      }),
                                  },
                              )}
                          </span>
                      </template>

                      <template id="cannot-subscribe-to-${context.name}-stream-tooltip-template">
                          <span>
                              ${$html_t(
                                  {defaultMessage: "Cannot subscribe to <z-stream></z-stream>"},
                                  {
                                      ["z-stream"]: () => ({
                                          __html: render_inline_decorated_stream_name({
                                              stream: context,
                                          }),
                                      }),
                                  },
                              )}
                          </span>
                      </template>

                      <svg
                          version="1.1"
                          xmlns="http://www.w3.org/2000/svg"
                          xmlns:xlink="http://www.w3.org/1999/xlink"
                          x="0px"
                          y="0px"
                          width="100%"
                          height="100%"
                          viewBox="0 0 512 512"
                          style="enable-background:new 0 0 512 512;"
                          xml:space="preserve"
                      >
                          <path
                              d="M459.319,229.668c0,22.201-17.992,40.193-40.205,40.193H269.85v149.271c0,22.207-17.998,40.199-40.196,40.193   c-11.101,0-21.149-4.492-28.416-11.763c-7.276-7.281-11.774-17.324-11.769-28.419l-0.006-149.288H40.181   c-11.094,0-21.134-4.492-28.416-11.774c-7.264-7.264-11.759-17.312-11.759-28.413C0,207.471,17.992,189.475,40.202,189.475h149.267   V40.202C189.469,17.998,207.471,0,229.671,0c22.192,0.006,40.178,17.986,40.19,40.187v149.288h149.282   C441.339,189.487,459.308,207.471,459.319,229.668z"
                          />
                      </svg>
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
