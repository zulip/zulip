import * as dialog_widget from "./dialog_widget";
import type {DialogWidgetConfig} from "./dialog_widget";
import {$t_html} from "./i18n";

export const launch = (conf: DialogWidgetConfig): string =>
    dialog_widget.launch({
        close_on_submit: true,
        focus_submit_on_open: true,
        html_submit_button: $t_html({defaultMessage: "Confirm"}),
        ...conf,
    });
