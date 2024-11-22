import {html, to_html} from "../../shared/src/html.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_confirm_delete_profile_field(context) {
    const out =
        context.count === 1
            ? $html_t(
                  {
                      defaultMessage:
                          "This will delete the <z-profile-field-name></z-profile-field-name> profile field for 1 user.",
                  },
                  {
                      ["z-profile-field-name"]: () =>
                          html`<strong>${context.profile_field_name}</strong>`,
                  },
              )
            : $html_t(
                  {
                      defaultMessage:
                          "This will delete the <z-profile-field-name></z-profile-field-name> profile field for <z-count></z-count> users.",
                  },
                  {
                      ["z-profile-field-name"]: () =>
                          html`<strong>${context.profile_field_name}</strong>`,
                      ["z-count"]: () => context.count,
                  },
              );
    return to_html(out);
}
