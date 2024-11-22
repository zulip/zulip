import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$html_t, $t} from "../src/i18n.ts";

export default function render_login_to_access(context) {
    const out = html`<div class="micromodal" id="login_to_access_modal" aria-hidden="true">
        <div class="modal__overlay" tabindex="-1">
            <div
                class="modal__container"
                role="dialog"
                aria-modal="true"
                aria-labelledby="login_to_access_modal_label"
            >
                <header class="modal__header">
                    <h1 class="modal__title" id="login_to_access_modal_label">
                        ${$t(
                            {defaultMessage: "Join {realm_name}"},
                            {realm_name: context.realm_name},
                        )}
                    </h1>
                    <button
                        class="modal__close"
                        aria-label="${$t({defaultMessage: "Close modal"})}"
                        data-micromodal-close
                    ></button>
                </header>
                <main class="modal__content">
                    ${to_bool(context.empty_narrow)
                        ? html`
                              <p>
                                  ${$html_t(
                                      {
                                          defaultMessage:
                                              "This is not a <z-link>publicly accessible</z-link> conversation.",
                                      },
                                      {
                                          ["z-link"]: (content) =>
                                              html`<a
                                                  target="_blank"
                                                  rel="noopener noreferrer"
                                                  href="/help/public-access-option"
                                                  >${content}</a
                                              >`,
                                      },
                                  )}
                              </p>
                          `
                        : ""}
                    <p>
                        ${$t({
                            defaultMessage:
                                "You can fully access this community and participate in conversations by creating a Zulip account in this organization.",
                        })}
                    </p>
                </main>
                <footer class="modal__footer">
                    <a class="modal__button dialog_submit_button" href="${context.signup_link}">
                        <span>${$t({defaultMessage: "Sign up"})}</span>
                    </a>
                    <a class="modal__button dialog_submit_button" href="${context.login_link}">
                        <span>${$t({defaultMessage: "Log in"})}</span>
                    </a>
                </footer>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
