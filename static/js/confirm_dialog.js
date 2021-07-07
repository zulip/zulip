import {$t_html} from "./i18n";
import * as dialog_widget from "./dialog_widget";

export function launch(conf) {
    dialog_widget.launch(
        {...conf,
         html_submit_button: $t_html({defaultMessage: "Confirm"}),
         is_confirm_dialog: true,
        });
}
