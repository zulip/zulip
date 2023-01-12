import $ from "jquery";

import {$t, $t_html} from "./i18n";
import * as loading from "./loading";
import * as ui_report from "./ui_report";

export function display_checkmark($elem) {
    const check_mark = document.createElement("img");
    check_mark.src = "/static/images/checkbox-green.svg";
    $elem.prepend(check_mark);
    $(check_mark).css("width", "13px");
}

export const strings = {
    success_html: $t_html({defaultMessage: "Saved"}),
    failure_html: $t_html({defaultMessage: "Save failed"}),
    saving: $t({defaultMessage: "Saving"}),
};

// Generic function for informing users about changes to the settings
// UI.  Intended to replace the old system that was built around
// direct calls to `ui_report`.
export function do_settings_change(
    request_method,
    url,
    data,
    status_element,
    {
        success_msg_html = strings.success_html,
        failure_msg_html = strings.failure_html,
        success_continuation,
        error_continuation,
        sticky = false,
        $error_msg_element,
    } = {},
) {
    const $spinner = $(status_element).expectOne();
    $spinner.fadeTo(0, 1);
    loading.make_indicator($spinner, {text: strings.saving});
    const remove_after = sticky ? undefined : 1000;
    const appear_after = 500;

    request_method({
        url,
        data,
        success(response_data) {
            setTimeout(() => {
                ui_report.success(success_msg_html, $spinner, remove_after);
                display_checkmark($spinner);
            }, appear_after);
            if (success_continuation !== undefined) {
                success_continuation(response_data);
            }
        },
        error(xhr) {
            if ($error_msg_element) {
                loading.destroy_indicator($spinner);
                ui_report.error(failure_msg_html, xhr, $error_msg_element);
            } else {
                ui_report.error(failure_msg_html, xhr, $spinner);
            }
            if (error_continuation !== undefined) {
                error_continuation(xhr);
            }
        },
    });
}

// This function is used to disable sub-setting when main setting is checked or unchecked
// or two settings are inter-dependent on their values.
// * is_checked is boolean, shows if the main setting is checked or not.
// * sub_setting_id is sub setting or setting which depend on main setting,
//   string id of setting.
// * disable_on_uncheck is boolean, true if sub setting should be disabled
//   when main setting unchecked.
export function disable_sub_setting_onchange(
    is_checked,
    sub_setting_id,
    disable_on_uncheck,
    include_label,
) {
    if ((is_checked && disable_on_uncheck) || (!is_checked && !disable_on_uncheck)) {
        $(`#${CSS.escape(sub_setting_id)}`).prop("disabled", false);
        if (include_label) {
            $(`#${CSS.escape(sub_setting_id)}_label`)
                .parent()
                .removeClass("control-label-disabled");
        }
    } else if ((is_checked && !disable_on_uncheck) || (!is_checked && disable_on_uncheck)) {
        $(`#${CSS.escape(sub_setting_id)}`).prop("disabled", true);
        if (include_label) {
            $(`#${CSS.escape(sub_setting_id)}_label`)
                .parent()
                .addClass("control-label-disabled");
        }
    }
}
