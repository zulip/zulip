import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";

export default function render_modal_banner(context, content) {
    const out = html`<div class="main-view-banner ${context.banner_type} ${context.classname}">
        <div class="main-view-banner-elements-wrapper">
            ${to_bool(context.banner_text)
                ? html` <p class="banner_content">${context.banner_text}</p> `
                : html` <div class="banner_content">${content(context)}</div> `}${to_bool(
                context.button_text,
            )
                ? to_bool(context.button_link)
                    ? html`
                          <a href="${context.button_link}">
                              <button
                                  class="main-view-banner-action-button${to_bool(
                                      context.hide_close_button,
                                  )
                                      ? " right_edge"
                                      : ""}"
                              >
                                  ${context.button_text}
                              </button>
                          </a>
                      `
                    : html`
                          <button
                              class="main-view-banner-action-button${to_bool(
                                  context.hide_close_button,
                              )
                                  ? " right_edge"
                                  : ""}"
                          >
                              ${context.button_text}
                          </button>
                      `
                : ""}
        </div>
        ${!to_bool(context.hide_close_button)
            ? html`
                  <a
                      role="button"
                      class="zulip-icon zulip-icon-close main-view-banner-close-button"
                  ></a>
              `
            : ""}
    </div> `;
    return to_html(out);
}
