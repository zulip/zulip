import {html, to_html} from "../shared/src/html.ts";
import {to_array, to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import {postprocess_content} from "../src/postprocess_content.ts";

export default function render_user_custom_profile_fields(context) {
    const out = to_array(context.profile_fields).map(
        (field) => html`
            <li
                data-type="${field.type}"
                class="field-section custom_user_field"
                data-field-id="${field.id}"
            >
                ${!to_bool(context.for_user_card_popover)
                    ? html` <div class="name">${field.name}</div> `
                    : ""}${to_bool(field.is_link)
                    ? html`
                          <div class="custom-user-url-field">
                              <a
                                  tabindex="0"
                                  href="${field.value}"
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  class="value custom-profile-fields-link ${to_bool(
                                      context.for_user_card_popover,
                                  )
                                      ? "tippy-zulip-tooltip"
                                      : ""}"
                                  data-tippy-content="${field.name}"
                                  >${field.value}</a
                              >
                              <span
                                  tabindex="0"
                                  class="copy-button copy-custom-field-url tippy-zulip-tooltip"
                                  aria-label="${$t({defaultMessage: "Copy URL"})}"
                                  data-tippy-content="${$t({defaultMessage: "Copy URL"})}"
                              >
                                  <i class="zulip-icon zulip-icon-copy" aria-hidden="true"></i>
                              </span>
                          </div>
                      `
                    : to_bool(field.is_external_account)
                      ? html`
                            <a
                                tabindex="0"
                                href="${field.link}"
                                target="_blank"
                                rel="noopener noreferrer"
                                class="value custom-profile-fields-link ${to_bool(
                                    context.for_user_card_popover,
                                )
                                    ? "tippy-zulip-tooltip"
                                    : ""}"
                                data-tippy-content="${field.name}"
                            >
                                ${field.subtype === "github"
                                    ? html` <i class="fa fa-github" aria-hidden="true"></i> `
                                    : field.subtype === "twitter"
                                      ? html` <i class="fa fa-twitter" aria-hidden="true"></i> `
                                      : ""}
                                ${field.value}
                            </a>
                        `
                      : to_bool(field.is_user_field)
                        ? html`
                              <div class="pill-container not-editable" data-field-id="${field.id}">
                                  <div
                                      class="input"
                                      contenteditable="false"
                                      style="display: none;"
                                  ></div>
                              </div>
                          `
                        : html`${to_bool(field.rendered_value)
                              ? html`
                                    <span
                                        class="value rendered_markdown ${to_bool(
                                            context.for_user_card_popover,
                                        )
                                            ? "tippy-zulip-tooltip"
                                            : ""}"
                                        data-tippy-content="${field.name}"
                                        >${{
                                            __html: postprocess_content(field.rendered_value),
                                        }}</span
                                    >
                                `
                              : html`            <span class="value ${to_bool(context.for_user_card_popover) ? html`tippy-zulip-tooltip"` : ""} data-tippy-content="${field.name}">${field.value}</span>
`} `}
            </li>
        `,
    );
    return to_html(out);
}
