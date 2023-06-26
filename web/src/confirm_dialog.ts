import * as dialog_widget from "./dialog_widget";
import type {DialogWidgetConfig} from "./dialog_widget";
import {$t_html} from "./i18n";

export function launch(conf: DialogWidgetConfig): void {
    dialog_widget.launch({
        ...conf,
        close_on_submit: true,
        focus_submit_on_open: true,
        html_submit_button: $t_html({defaultMessage: "Confirm"}),
        // Used to control button colors in the template.
    });
}
