import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import {postprocess_content} from "../../src/postprocess_content.ts";
import render_icon_button from "../components/icon_button.ts";

export default function render_admin_channel_folder_list_item(context) {
    const out = html`<tr
        class="channel-folder-row movable-row"
        data-channel-folder-id="${context.id}"
    >
        <td>
            ${to_bool(context.is_admin)
                ? html`
                      <span class="move-handle">
                          <i class="fa fa-ellipsis-v" aria-hidden="true"></i>
                          <i class="fa fa-ellipsis-v" aria-hidden="true"></i>
                      </span>
                  `
                : ""} <span class="channel-folder-name">${context.folder_name}</span>
        </td>
        <td>
            <span class="channel-folder-description rendered-markdown"
                >${{__html: postprocess_content(context.rendered_description)}}</span
            >
        </td>
        ${to_bool(context.is_admin)
            ? html`
                  <td class="actions">
                      ${{
                          __html: render_icon_button({
                              ["data-tippy-content"]: $t({defaultMessage: "Manage folder"}),
                              custom_classes:
                                  "tippy-zulip-delayed-tooltip edit-channel-folder-button",
                              intent: "neutral",
                              icon: "folder-cog",
                          }),
                      }}
                      ${{
                          __html: render_icon_button({
                              ["aria-label"]: $t({defaultMessage: "Delete"}),
                              ["data-tippy-content"]: $t({defaultMessage: "Delete"}),
                              custom_classes:
                                  "tippy-zulip-delayed-tooltip archive-channel-folder-button",
                              intent: "danger",
                              icon: "trash",
                          }),
                      }}
                  </td>
              `
            : ""}
    </tr> `;
    return to_html(out);
}
