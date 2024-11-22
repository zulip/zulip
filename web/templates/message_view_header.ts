import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import {postprocess_content} from "../src/postprocess_content.ts";
import render_navbar_icon_and_title from "./navbar_icon_and_title.ts";

export default function render_message_view_header(context) {
    const out = to_bool(context.stream_settings_link)
        ? html`${!to_bool(context.stream.is_archived)
                  ? html`<a
                            class="message-header-stream-settings-button tippy-zulip-tooltip"
                            data-tooltip-template-id="stream-details-tooltip-template"
                            data-tippy-placement="bottom"
                            href="${context.stream_settings_link}"
                        >
                            ${{__html: render_navbar_icon_and_title(context)}}</a
                        >
                        <template id="stream-details-tooltip-template">
                            <div>
                                <div>${$t({defaultMessage: "Go to channel settings"})}</div>
                                ${!to_bool(context.is_spectator)
                                    ? html`
                                          <div class="tooltip-inner-content italic">
                                              ${$t(
                                                  {
                                                      defaultMessage:
                                                          "This channel has {sub_count, plural, =0 {no subscribers} one {# subscriber} other {# subscribers}}.",
                                                  },
                                                  {sub_count: context.sub_count},
                                              )}
                                          </div>
                                      `
                                    : ""}
                            </div>
                        </template> `
                  : html`<span class="navbar_title">
                        ${{__html: render_navbar_icon_and_title(context)}}</span
                    > `}<span
                  class="narrow_description rendered_markdown single-line-rendered-markdown"
              >
                  ${to_bool(context.rendered_narrow_description)
                      ? html`
                            ${{__html: postprocess_content(context.rendered_narrow_description)}}
                        `
                      : to_bool(context.is_admin)
                        ? html`
                              <a href="${context.stream_settings_link}">
                                  ${$t({defaultMessage: "Add a description"})}
                              </a>
                          `
                        : ""}</span
              > `
        : html`<span class="navbar_title"> ${{__html: render_navbar_icon_and_title(context)}}</span>
              ${to_bool(context.description)
                  ? html`
                        <span
                            class="narrow_description rendered_markdown single-line-rendered-markdown"
                            >${context.description}
                            ${to_bool(context.link)
                                ? html`
                                      <a
                                          class="help_link_widget"
                                          href="${context.link}"
                                          target="_blank"
                                          rel="noopener noreferrer"
                                      >
                                          <i class="fa fa-question-circle-o" aria-hidden="true"></i>
                                      </a>
                                  `
                                : ""}
                        </span>
                    `
                  : ""}`;
    return to_html(out);
}
