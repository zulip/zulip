import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_icon_button from "../components/icon_button.ts";

export default function render_admin_export_list(context) {
    const out = ((realm_export) =>
        html`<tr
            class="export_row"
            id="export_${realm_export.id}"
            data-export-id="${realm_export.id}"
        >
            <td>
                <span class="acting_user">${realm_export.acting_user}</span>
            </td>
            <td>
                <span>${realm_export.export_type_description}</span>
            </td>
            <td>
                <span class="export_time">${realm_export.event_time}</span>
            </td>
            <td>
                ${to_bool(realm_export.url)
                    ? html`
                          <span class="export_url"
                              ><a href="${realm_export.url}" download
                                  >${$t({defaultMessage: "Complete"})}</a
                              ></span
                          >
                      `
                    : to_bool(realm_export.time_failed)
                      ? html`
                            <span class="export_status"
                                >${$t({defaultMessage: "Failed"})}:
                                ${realm_export.time_failed}</span
                            >
                        `
                      : to_bool(realm_export.pending)
                        ? html` <div class="export_url_spinner"></div> `
                        : to_bool(realm_export.time_deleted)
                          ? html`
                                <span class="export_status"
                                    >${$t({defaultMessage: "Deleted"})}:
                                    ${realm_export.time_deleted}</span
                                >
                            `
                          : ""}
            </td>
            <td class="actions">
                ${to_bool(realm_export.url)
                    ? html` ${{
                          __html: render_icon_button({
                              ["aria-label"]: $t({defaultMessage: "Delete"}),
                              ["data-tippy-content"]: $t({defaultMessage: "Delete"}),
                              custom_classes: "tippy-zulip-delayed-tooltip delete",
                              intent: "danger",
                              icon: "trash",
                          }),
                      }}`
                    : ""}
            </td>
        </tr> `)(context.realm_export);
    return to_html(out);
}
