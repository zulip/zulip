import {html, to_html} from "../shared/src/html.ts";
import {to_array, to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_send_later_modal_options(context) {
    const out = html`<div id="send_later_options">
        <ul class="send_later_list">
            ${to_bool(context.possible_send_later_today)
                ? Object.entries(context.possible_send_later_today).map(
                      ([option_key, option]) => html`
                          <li>
                              <a
                                  id="${option_key}"
                                  class="send_later_today send_later_option"
                                  data-send-stamp="${option.stamp}"
                                  tabindex="0"
                                  >${option.text}</a
                              >
                          </li>
                      `,
                  )
                : ""}${Object.entries(context.send_later_tomorrow).map(
                ([option_key, option]) => html`
                    <li>
                        <a
                            id="${option_key}"
                            class="send_later_tomorrow send_later_option"
                            data-send-stamp="${option.stamp}"
                            tabindex="0"
                            >${option.text}</a
                        >
                    </li>
                `,
            )}${to_bool(context.possible_send_later_monday)
                ? Object.entries(context.possible_send_later_monday).map(
                      ([option_key, option]) => html`
                          <li>
                              <a
                                  id="${option_key}"
                                  class="send_later_monday send_later_option"
                                  data-send-stamp="${option.stamp}"
                                  tabindex="0"
                                  >${option.text}</a
                              >
                          </li>
                      `,
                  )
                : ""}
            <li>
                <a class="send_later_custom send_later_option" tabindex="0"
                    >${$t({defaultMessage: "Custom time"})}</a
                >
            </li>
        </ul>
    </div> `;
    return to_html(out);
}
