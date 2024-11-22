import {html, to_html} from "../../../shared/src/html.ts";
import {to_array, to_bool} from "../../../src/hbs_compat.ts";
import {$t} from "../../../src/i18n.ts";
import {postprocess_content} from "../../../src/postprocess_content.ts";

export default function render_user_card_popover_custom_fields(context) {
    const out = to_array(context.profile_fields).map(
        (field) => html`
            <li
                role="none"
                class="popover-menu-list-item text-item custom_user_field"
                data-type="${field.type}"
                data-field-id="${field.id}"
            >
                ${to_bool(field.is_link)
                    ? html`
                          <a
                              href="${field.value}"
                              target="_blank"
                              rel="noopener noreferrer"
                              class="custom-profile-field-value custom-profile-field-link"
                              data-tippy-content="${field.name}"
                              tabindex="0"
                          >
                              <span class="custom-profile-field-text">${field.value}</span>
                          </a>
                          <span
                              role="menuitem"
                              tabindex="0"
                              class="popover-menu-link copy-button copy-custom-profile-field-link"
                              aria-label="${$t({defaultMessage: "Copy URL"})}"
                              data-tippy-content="${$t({defaultMessage: "Copy URL"})}"
                          >
                              <i class="zulip-icon zulip-icon-copy" aria-hidden="true"></i>
                          </span>
                      `
                    : to_bool(field.is_external_account)
                      ? html`
                            <a
                                href="${field.link}"
                                target="_blank"
                                rel="noopener noreferrer"
                                class="custom-profile-field-value custom-profile-field-link"
                                data-tippy-content="${field.name}"
                                tabindex="0"
                            >
                                ${field.subtype === "github"
                                    ? html`
                                          <i
                                              class="popover-menu-icon fa fa-github"
                                              aria-hidden="true"
                                          ></i>
                                      `
                                    : field.subtype === "twitter"
                                      ? html`
                                            <i
                                                class="popover-menu-icon fa fa-twitter"
                                                aria-hidden="true"
                                            ></i>
                                        `
                                      : ""}
                                <span class="custom-profile-field-text">${field.value}</span>
                            </a>
                        `
                      : to_bool(field.rendered_value)
                        ? html`
                              <div
                                  class="custom-profile-field-value rendered_markdown"
                                  data-tippy-content="${field.name}"
                              >
                                  ${{__html: postprocess_content(field.rendered_value)}}
                              </div>
                          `
                        : html`
                              <div
                                  class="custom-profile-field-value"
                                  data-tippy-content="${field.name}"
                              >
                                  <span class="custom-profile-field-text">${field.value}</span>
                              </div>
                          `}
            </li>
        `,
    );
    return to_html(out);
}
