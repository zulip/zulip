import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_compose_banner(context, content) {
    const out = html`<div
        class="main-view-banner ${context.banner_type} ${context.classname}"
        ${to_bool(context.user_id) ? html`data-user-id="${context.user_id}"` : ""}
        ${to_bool(context.stream_id) ? html`data-stream-id="${context.stream_id}"` : ""}
        ${to_bool(context.topic_name) ? html`data-topic-name="${context.topic_name}"` : ""}
    >
        <div class="main-view-banner-elements-wrapper">
            ${to_bool(context.banner_text)
                ? html` <p class="banner_content">${context.banner_text}</p> `
                : html` <div class="banner_content">${content(context)}</div> `}${to_bool(
                context.button_text,
            )
                ? html`
                      <button
                          class="main-view-banner-action-button${to_bool(context.hide_close_button)
                              ? " right_edge"
                              : ""}"
                          ${to_bool(context.scheduling_message)
                              ? html`data-validation-trigger="schedule"`
                              : ""}
                      >
                          ${context.button_text}
                      </button>
                  `
                : ""}${to_bool(context.is_onboarding_banner)
                ? html`
                      <button
                          class="main-view-banner-action-button right_edge"
                          data-action="mark-as-read"
                      >
                          ${$t({defaultMessage: "Got it"})}
                      </button>
                  `
                : ""}
        </div>
        ${to_bool(context.hide_close_button)
            ? /* hide_close_button is null by default, and false if explicitly set as false. */ ""
            : html`
                  <a
                      role="button"
                      class="zulip-icon zulip-icon-close main-view-banner-close-button"
                  ></a>
              `}
    </div> `;
    return to_html(out);
}
