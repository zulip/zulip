import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_bot_settings(context) {
    const out = html`<div id="bot-settings" class="settings-section" data-name="your-bots">
        <div class="bot-settings-form">
            ${!to_bool(context.current_user.is_guest)
                ? html`
                      <div class="tip">
                          ${$html_t(
                              {
                                  defaultMessage:
                                      "Looking for our <z-integrations>integrations</z-integrations> or <z-api>API</z-api> documentation?",
                              },
                              {
                                  ["z-integrations"]: (content) =>
                                      html`<a
                                          href="/integrations/"
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          >${content}</a
                                      >`,
                                  ["z-api"]: (content) =>
                                      html`<a href="/api/" target="_blank" rel="noopener noreferrer"
                                          >${content}</a
                                      >`,
                              },
                          )}
                      </div>
                      <div class="bot-settings-tip" id="personal-bot-settings-tip"></div>
                      <div>
                          <button
                              class="button rounded sea-green add-a-new-bot ${!to_bool(
                                  context.can_create_new_bots,
                              )
                                  ? "hide"
                                  : ""}"
                          >
                              ${$t({defaultMessage: "Add a new bot"})}
                          </button>
                      </div>
                  `
                : ""}
            <hr />

            <div class="tab-container"></div>

            <div
                id="active_bots_list_container"
                class="bots_section"
                data-bot-settings-section="active-bots"
            >
                <div class="config-download-text">
                    <span
                        >${$t({
                            defaultMessage:
                                "Download config of all active outgoing webhook bots in Zulip Botserver format.",
                        })}</span
                    >
                    <a
                        type="submit"
                        download="${context.botserverrc}"
                        id="download_botserverrc"
                        class="bootstrap-btn tippy-zulip-delayed-tooltip"
                        data-tippy-content="${$t({defaultMessage: "Download botserverrc"})}"
                    >
                        <i class="fa fa-download sea-green" aria-hidden="true"></i>
                    </a>
                </div>
                <ol
                    id="active_bots_list"
                    class="bots_list"
                    data-empty="${$t({defaultMessage: "You have no active bots."})}"
                ></ol>
            </div>

            <div
                id="inactive_bots_list_container"
                class="bots_section"
                data-bot-settings-section="inactive-bots"
            >
                <ol
                    id="inactive_bots_list"
                    class="bots_list"
                    data-empty="${$t({defaultMessage: "You have no inactive bots."})}"
                ></ol>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
