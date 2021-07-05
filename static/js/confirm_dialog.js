import * as dialog_widget from "./dialog_widget";

export function launch(conf) {
    dialog_widget.launch({...conf, is_confirm_dialog: true});
}
