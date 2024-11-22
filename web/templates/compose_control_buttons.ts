import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import render_compose_control_buttons_in_popover from "./popovers/compose_control_buttons/compose_control_buttons_in_popover.ts";
import render_compose_control_buttons_in_popover_2 from "./popovers/compose_control_buttons/compose_control_buttons_in_popover_2.ts";

export default function render_compose_control_buttons(context) {
    const out = html`<div class="compose-control-buttons-container order-1">
        <input type="file" class="file_input notvisible" multiple />
        <div
            class="compose_control_button_container"
            data-tooltip-template-id="preview-tooltip"
            data-tippy-maxWidth="none"
        >
            <a
                role="button"
                class="markdown_preview compose_control_button zulip-icon zulip-icon-preview"
                aria-label="${$t({defaultMessage: "Preview"})}"
                tabindex="0"
            ></a>
        </div>
        <div
            class="compose_control_button_container"
            data-tippy-content="${$t({defaultMessage: "Write"})}"
        >
            <a
                role="button"
                class="undo_markdown_preview compose_control_button zulip-icon zulip-icon-compose-edit"
                aria-label="${$t({defaultMessage: "Write"})}"
                tabindex="0"
                style="display:none;"
            ></a>
        </div>
        ${to_bool(context.file_upload_enabled)
            ? html`
                  <div
                      class="compose_control_button_container preview_mode_disabled"
                      data-tippy-content="${$t({defaultMessage: "Upload files"})}"
                  >
                      <a
                          role="button"
                          class="compose_control_button compose_upload_file zulip-icon zulip-icon-attachment"
                          aria-label="${$t({defaultMessage: "Upload files"})}"
                          tabindex="0"
                      ></a>
                  </div>
              `
            : ""}
        <div
            class="compose_control_button_container preview_mode_disabled"
            data-tippy-content="${$t({defaultMessage: "Add video call"})}"
        >
            <a
                role="button"
                class="compose_control_button zulip-icon zulip-icon-video-call video_link"
                aria-label="${$t({defaultMessage: "Add video call"})}"
                tabindex="0"
            ></a>
        </div>
        <div
            class="compose_control_button_container preview_mode_disabled"
            data-tippy-content="${$t({defaultMessage: "Add voice call"})}"
        >
            <a
                role="button"
                class="compose_control_button zulip-icon zulip-icon-voice-call audio_link"
                aria-label="${$t({defaultMessage: "Add voice call"})}"
                tabindex="0"
            ></a>
        </div>
        <div class="divider">|</div>
        <div
            class="compose_control_button_container preview_mode_disabled"
            data-tippy-content="${$t({defaultMessage: "Add emoji"})}"
        >
            <a
                role="button"
                class="compose_control_button zulip-icon zulip-icon-smile-bigger emoji_map"
                aria-label="${$t({defaultMessage: "Add emoji"})}"
                tabindex="0"
            ></a>
        </div>
        <div
            class="compose_control_button_container preview_mode_disabled"
            data-tooltip-template-id="add-global-time-tooltip"
            data-tippy-maxWidth="none"
        >
            <a
                role="button"
                class="compose_control_button zulip-icon zulip-icon-time time_pick"
                aria-label="${$t({defaultMessage: "Add global time"})}"
                tabindex="0"
            ></a>
        </div>
        ${!to_bool(context.message_id)
            ? html`
                  <div
                      class="compose_control_button_container preview_mode_disabled"
                      data-tooltip-template-id="add-poll-tooltip"
                      data-tippy-maxWidth="none"
                  >
                      <a
                          role="button"
                          class="compose_control_button zulip-icon zulip-icon-poll add-poll"
                          aria-label="${$t({defaultMessage: "Add poll"})}"
                          tabindex="0"
                      ></a>
                  </div>
              `
            : ""}
        <div
            class="compose_control_button_container ${!to_bool(context.giphy_enabled)
                ? "hide"
                : ""} preview_mode_disabled"
            data-tippy-content="${$t({defaultMessage: "Add GIF"})}"
        >
            <a
                role="button"
                class="compose_control_button compose_gif_icon zulip-icon zulip-icon-gif"
                aria-label="${$t({defaultMessage: "Add GIF"})}"
                tabindex="0"
            ></a>
        </div>
        <div class="show_popover_buttons_2">
            <div class="divider">|</div>
            ${{__html: render_compose_control_buttons_in_popover_2(context)}}
        </div>
        <div class="show_popover_buttons">
            <div class="divider">|</div>
            ${{__html: render_compose_control_buttons_in_popover(context)}}
        </div>
        <div class="compose_control_menu_wrapper" role="button" tabindex="0">
            <a
                class="compose_control_button zulip-icon zulip-icon-more-vertical hide compose_control_menu"
                tabindex="-1"
                data-tippy-content="Compose actions"
            ></a>
        </div>
    </div> `;
    return to_html(out);
}
