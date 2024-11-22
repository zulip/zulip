import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_bot_avatar_row(context) {
    const out = html`<li class="bot-information-box white-box">
        <div class="bot-card-image overflow-hidden">
            <img src="${context.avatar_url}" class="bot-card-avatar" />
            <div class="bot-card-details">
                <div class="bot-card-name">${context.name}</div>
                ${to_bool(context.is_active)
                    ? html`
                          <div class="edit-bot-buttons">
                              <button
                                  type="submit"
                                  class="bootstrap-btn open_edit_bot_form tippy-zulip-delayed-tooltip"
                                  data-sidebar-form="edit-bot"
                                  data-tippy-content="${$t({defaultMessage: "Edit bot"})}"
                                  data-email="${context.email}"
                              >
                                  <i class="fa fa-pencil blue" aria-hidden="true"></i>
                              </button>
                              <a
                                  type="submit"
                                  download="${context.zuliprc}"
                                  class="bootstrap-btn download_bot_zuliprc tippy-zulip-delayed-tooltip"
                                  data-tippy-content="${$t({defaultMessage: "Download zuliprc"})}"
                                  data-email="${context.email}"
                              >
                                  <i class="fa fa-download sea-green" aria-hidden="true"></i>
                              </a>
                              <button
                                  type="submit"
                                  id="copy_zuliprc"
                                  class="bootstrap-btn copy_zuliprc tippy-zulip-delayed-tooltip"
                                  data-tippy-content="${$t({defaultMessage: "Copy zuliprc"})}"
                              >
                                  <i class="zulip-icon zulip-icon-copy" aria-hidden="true"></i>
                              </button>
                              <button
                                  type="submit"
                                  class="bootstrap-btn deactivate_bot danger-red tippy-zulip-delayed-tooltip"
                                  data-tippy-content="${$t({defaultMessage: "Deactivate bot"})}"
                                  data-user-id="${context.user_id}"
                              >
                                  <i class="fa fa-user-times" aria-hidden="true"></i>
                              </button>
                              <button
                                  type="submit"
                                  class="bootstrap-btn open_bots_subscribed_streams tippy-zulip-delayed-tooltip"
                                  data-tippy-content="${$t({
                                      defaultMessage: "Subscribed channels",
                                  })}"
                                  data-user-id="${context.user_id}"
                              >
                                  <i class="fa fa-hashtag purple" aria-hidden="true"></i>
                              </button>
                              ${to_bool(context.is_incoming_webhook_bot)
                                  ? html`
                                        <button
                                            type="submit"
                                            class="bootstrap-btn open-generate-integration-url-modal tippy-zulip-delayed-tooltip"
                                            data-tippy-content="${$t({
                                                defaultMessage: "Generate URL for an integration",
                                            })}"
                                            data-api-key="${context.api_key}"
                                        >
                                            <i class="fa fa-link steel-blue" aria-hidden="true"></i>
                                        </button>
                                    `
                                  : ""}
                          </div>
                      `
                    : ""}
            </div>
        </div>
        <div class="bot-card-info" data-user-id="${context.user_id}">
            <div class="bot-card-type">
                <div class="bot-card-field">${$t({defaultMessage: "Bot type"})}</div>
                <div class="bot-card-value">${context.type}</div>
            </div>
            <div class="bot-card-email">
                <div class="bot-card-field">${$t({defaultMessage: "Bot email"})}</div>
                <div class="bot-card-value">${context.email}</div>
            </div>
            ${to_bool(context.is_active)
                ? html`
                      <div class="bot-card-api-key">
                          <span class="bot-card-field">${$t({defaultMessage: "API key"})}</span>
                          <div class="bot-card-api-key-value-and-button no-select">
                              <!-- have the \`.text-select\` in \`.no-select\` so that the value doesn't have trailing whitespace. -->
                              <span class="bot-card-value text-select">${context.api_key}</span>
                              <button
                                  type="submit"
                                  class="button no-style bot-card-regenerate-bot-api-key tippy-zulip-delayed-tooltip"
                                  data-tippy-content="${$t({
                                      defaultMessage: "Generate new API key",
                                  })}"
                                  data-user-id="${context.user_id}"
                              >
                                  <i class="fa fa-refresh" aria-hidden="true"></i>
                              </button>
                          </div>
                          <div class="bot-card-api-key-error text-error"></div>
                      </div>
                  `
                : html`
                      <button
                          class="button round button-warning reactivate_bot"
                          data-user-id="${context.user_id}"
                      >
                          ${$t({defaultMessage: "Reactivate bot"})}
                      </button>
                  `}
        </div>
    </li> `;
    return to_html(out);
}
