import $ from "jquery";

import render_add_default_streams from "../templates/settings/add_default_streams.hbs";
import render_admin_default_streams_list from "../templates/settings/admin_default_streams_list.hbs";
import render_default_stream_choice from "../templates/settings/default_stream_choice.hbs";

import * as channel from "./channel";
import * as dialog_widget from "./dialog_widget";
import * as dropdown_widget from "./dropdown_widget";
import * as hash_parser from "./hash_parser";
import {$t_html} from "./i18n";
import * as ListWidget from "./list_widget";
import * as loading from "./loading";
import * as scroll_util from "./scroll_util";
import * as settings_profile_fields from "./settings_profile_fields";
import {current_user} from "./state_data";
import * as stream_data from "./stream_data";
import * as sub_store from "./sub_store";
import * as ui_report from "./ui_report";

function add_choice_row($widget) {
    if ($widget.closest(".choice-row").next().hasClass("choice-row")) {
        return;
    }
    create_choice_row();
}

function get_chosen_default_streams() {
    // Return the set of stream id's of streams chosen in the default stream modal.
    return new Set(
        $("#default-stream-choices .choice-row .dropdown_widget_value")
            .map((_i, elem) => Number($(elem).attr("data-stream-id")).toString())
            .get(),
    );
}

function create_choice_row() {
    const $container = $("#default-stream-choices");
    const value = settings_profile_fields.get_value_for_new_option("#default-stream-choices");
    const stream_dropdown_widget_name = `select_default_stream_${value}`;
    const row_html = render_default_stream_choice({value, stream_dropdown_widget_name});
    $container.append($(row_html));

    // List of non-default streams that are not yet selected.
    function get_options() {
        const chosen_default_streams = get_chosen_default_streams();

        return stream_data
            .get_non_default_stream_names()
            .filter((e) => !chosen_default_streams.has(e.unique_id));
    }

    function item_click_callback(event, dropdown) {
        const $selected_stream = $(event.currentTarget);
        const selected_stream_name = $selected_stream.attr("data-name");
        const selected_stream_id = Number.parseInt($selected_stream.data("unique-id"), 10);

        const $stream_dropdown_widget = $(`#${CSS.escape(stream_dropdown_widget_name)}_widget`);
        const $stream_name = $stream_dropdown_widget.find(".dropdown_widget_value");
        $stream_name.text(selected_stream_name);
        $stream_name.attr("data-stream-id", selected_stream_id);

        add_choice_row($stream_dropdown_widget);
        dropdown.hide();
        $("#add-default-stream-modal .dialog_submit_button").prop("disabled", false);
        event.stopPropagation();
        event.preventDefault();
    }

    new dropdown_widget.DropdownWidget({
        widget_name: stream_dropdown_widget_name,
        get_options,
        item_click_callback,
        $events_container: $container,
        tippy_props: {
            placement: "bottom-start",
        },
    }).setup();
}

const meta = {
    loaded: false,
};

export function reset() {
    meta.loaded = false;
}

export function maybe_disable_widgets() {
    if (current_user.is_admin) {
        return;
    }

    $(".organization-box [data-name='default-streams-list']")
        .find("input:not(.search), button, select")
        .prop("disabled", true);
}

export function build_default_stream_table() {
    const $table = $("#admin_default_streams_table").expectOne();

    const stream_ids = stream_data.get_default_stream_ids();
    const subs = stream_ids.map((stream_id) => sub_store.get(stream_id));

    ListWidget.create($table, subs, {
        name: "default_streams_list",
        get_item: ListWidget.default_get_item,
        modifier_html(item) {
            return render_admin_default_streams_list({
                stream: item,
                can_modify: current_user.is_admin,
            });
        },
        filter: {
            $element: $table.closest(".settings-section").find(".search"),
            predicate(item, query) {
                return item.name.toLowerCase().includes(query.toLowerCase());
            },
            onupdate() {
                scroll_util.reset_scrollbar($table);
            },
        },
        $parent_container: $("#admin-default-streams-list").expectOne(),
        init_sort: "name_alphabetic",
        sort_fields: {
            ...ListWidget.generic_sort_functions("alphabetic", ["name"]),
        },
        $simplebar_container: $("#admin-default-streams-list .progressive-table-wrapper"),
    });

    loading.destroy_indicator($("#admin_page_default_streams_loading_indicator"));
}

export function update_default_streams_table() {
    if (["organization", "settings"].includes(hash_parser.get_current_hash_category())) {
        $("#admin_default_streams_table").expectOne().find("tr.default_stream_row").remove();
        build_default_stream_table();
    }
}

export function delete_default_stream(stream_id, $default_stream_row, $alert_element) {
    channel.del({
        url: "/json/default_streams?" + $.param({stream_id}),
        error(xhr) {
            ui_report.generic_row_button_error(xhr, $alert_element);
        },
        success() {
            $default_stream_row.remove();
        },
    });
}

function delete_choice_row(e) {
    const $row = $(e.currentTarget).parent();
    $row.remove();

    // Disable the submit button if no streams are selected.
    $("#add-default-stream-modal .dialog_submit_button").prop(
        "disabled",
        $(".choice-row").length <= 1,
    );
}

function show_add_default_streams_modal() {
    const html_body = render_add_default_streams();

    function add_default_streams(e) {
        e.preventDefault();
        e.stopPropagation();

        // Keep track of the number of successful requests. Close the modal
        // only if all the requests are successful.
        let successful_requests = 0;
        const chosen_streams = get_chosen_default_streams();

        function make_default_stream_request(stream_id) {
            const data = {stream_id};
            channel.post({
                url: "/json/default_streams",
                data,
                success() {
                    successful_requests = successful_requests + 1;

                    if (successful_requests === chosen_streams.size) {
                        dialog_widget.close();
                    }
                },
                error(xhr) {
                    ui_report.error(
                        $t_html({defaultMessage: "Failed adding one or more channels."}),
                        xhr,
                        $("#dialog_error"),
                    );
                    dialog_widget.hide_dialog_spinner();
                },
            });
        }

        for (const chosen_stream of chosen_streams) {
            make_default_stream_request(chosen_stream);
        }
    }

    function default_stream_post_render() {
        $("#add-default-stream-modal .dialog_submit_button").prop("disabled", true);

        create_choice_row();
        $("#default-stream-choices").on("click", "button.delete-choice", delete_choice_row);
    }

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Add default channels"}),
        html_body,
        html_submit_button: $t_html({defaultMessage: "Add"}),
        help_link: "/help/set-default-channels-for-new-users",
        id: "add-default-stream-modal",
        loading_spinner: true,
        on_click: add_default_streams,
        post_render: default_stream_post_render,
    });
}

export function set_up() {
    build_page();
    maybe_disable_widgets();
}

export function build_page() {
    meta.loaded = true;

    update_default_streams_table();

    $("#show-add-default-streams-modal").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();

        show_add_default_streams_modal();
    });

    $("body").on("click", ".default_stream_row .remove-default-stream", function (e) {
        const $row = $(this).closest(".default_stream_row");
        const stream_id = Number.parseInt($row.attr("data-stream-id"), 10);
        delete_default_stream(stream_id, $row, $(e.target));
    });
}
