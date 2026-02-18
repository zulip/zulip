import $ from "jquery";
import * as tippy from "tippy.js";

import * as channel_folders from "./channel_folders.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import type {DropdownWidgetOptions} from "./dropdown_widget.ts";
import {$t} from "./i18n.ts";
import * as stream_data from "./stream_data.ts";
import {LONG_HOVER_DELAY} from "./tippyjs.ts";
import * as util from "./util.ts";

export const FOLDER_FILTERS = {
    UNCATEGORIZED_DROPDOWN_OPTION: -1,
    ANY_FOLDER_DROPDOWN_OPTION: -2,
} as const;

export type FolderFilterDropdownWidgetConfig = {
    widget_name: string;
    widget_selector: string;
    item_click_callback: DropdownWidgetOptions["item_click_callback"];
    $events_container: JQuery;
    default_id: number;
};

export function get_folder_filter_dropdown_options(
    current_value: string | number | undefined,
): dropdown_widget.Option[] {
    const folder_filters = FOLDER_FILTERS;

    const folders = channel_folders.get_folders_with_accessible_channels();
    const options: dropdown_widget.Option[] = folders.map((folder) => ({
        name: folder.name,
        unique_id: folder.id,
        bold_current_selection: current_value === folder.id,
    }));

    // Show "Uncategorized" option only if user can access at least
    // one channel that is uncategorized.
    const show_uncategorized_option = stream_data
        .get_unsorted_subs()
        .some((sub) => sub.folder_id === null);
    if (show_uncategorized_option) {
        const uncategorized_option = {
            is_setting_disabled: true,
            show_disabled_icon: false,
            show_disabled_option_name: true,
            unique_id: folder_filters.UNCATEGORIZED_DROPDOWN_OPTION,
            name: $t({defaultMessage: "Uncategorized"}),
            bold_current_selection: current_value === folder_filters.UNCATEGORIZED_DROPDOWN_OPTION,
        };
        options.unshift(uncategorized_option);
    }

    const any_folder_option = {
        is_setting_disabled: true,
        show_disabled_icon: false,
        show_disabled_option_name: true,
        unique_id: folder_filters.ANY_FOLDER_DROPDOWN_OPTION,
        name: $t({defaultMessage: "Any folder"}),
        bold_current_selection: current_value === folder_filters.ANY_FOLDER_DROPDOWN_OPTION,
    };
    options.unshift(any_folder_option);

    return options;
}

export function create_folder_filter_dropdown_widget(
    config: FolderFilterDropdownWidgetConfig,
): dropdown_widget.DropdownWidget {
    const widget = new dropdown_widget.DropdownWidget({
        widget_name: config.widget_name,
        widget_selector: config.widget_selector,
        get_options: get_folder_filter_dropdown_options,
        item_click_callback: config.item_click_callback,
        $events_container: config.$events_container,
        unique_id_type: "number",
        default_id: config.default_id,
    });

    return widget;
}

export function update_tooltip_for_folder_filter(
    reference_element_id: string,
    folder_filter_value: number,
): void {
    // Destroy the previous tooltip instance.
    $<tippy.PopperElement>(`#${reference_element_id}`)[0]?._tippy?.destroy();

    const folder_filters = FOLDER_FILTERS;

    let content;
    if (folder_filter_value === folder_filters.ANY_FOLDER_DROPDOWN_OPTION) {
        content = $t({defaultMessage: "Filter by folder"});
    } else if (folder_filter_value === folder_filters.UNCATEGORIZED_DROPDOWN_OPTION) {
        content = $t({defaultMessage: "Viewing uncategorized channels"});
    } else {
        const folder = channel_folders.get_channel_folder_by_id(folder_filter_value);
        content = $t(
            {defaultMessage: "Viewing channels in {folder_name}"},
            {folder_name: folder.name},
        );
    }

    tippy.default(util.the($(`#${reference_element_id}`)), {
        animation: false,
        hideOnClick: false,
        placement: "bottom",
        appendTo: () => document.body,
        delay: LONG_HOVER_DELAY,
        content,
    });
}
