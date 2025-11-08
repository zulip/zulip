import $ from "jquery";

import render_confirm_delete_playground from "../templates/confirm_dialog/confirm_delete_playground.hbs";
import render_admin_playground_list from "../templates/settings/admin_playground_list.hbs";

import {Typeahead} from "./bootstrap_typeahead.ts";
import * as bootstrap_typeahead from "./bootstrap_typeahead.ts";
import type {TypeaheadInputElement} from "./bootstrap_typeahead.ts";
import * as channel from "./channel.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import * as ListWidget from "./list_widget.ts";
import * as realm_playground from "./realm_playground.ts";
import type {RealmPlayground} from "./realm_playground.ts";
import * as scroll_util from "./scroll_util.ts";
import {current_user, realm} from "./state_data.ts";
import {render_typeahead_item} from "./typeahead_helper.ts";
import * as ui_report from "./ui_report.ts";
import * as util from "./util.ts";

let pygments_typeahead: Typeahead<string>;

const meta = {
    loaded: false,
};

export function reset(): void {
    meta.loaded = false;
}

export function maybe_disable_widgets(): void {
    if (current_user.is_admin) {
        return;
    }
}

export function populate_playgrounds(playgrounds_data: RealmPlayground[]): void {
    if (!meta.loaded) {
        return;
    }
    const $playgrounds_table = $("#admin_playgrounds_table").expectOne();
    ListWidget.create<RealmPlayground>($playgrounds_table, playgrounds_data, {
        name: "playgrounds_list",
        get_item: ListWidget.default_get_item,
        modifier_html(playground) {
            return render_admin_playground_list({
                playground: {
                    playground_name: playground.name,
                    pygments_language: playground.pygments_language,
                    url_template: playground.url_template,
                    id: playground.id,
                },
                can_modify: current_user.is_admin,
            });
        },
        filter: {
            $element: $playgrounds_table
                .closest(".settings-section")
                .find<HTMLInputElement>("input.search"),
            predicate(item, value) {
                return (
                    item.name.toLowerCase().includes(value) ||
                    item.pygments_language.toLowerCase().includes(value)
                );
            },
            onupdate() {
                scroll_util.reset_scrollbar($playgrounds_table);
            },
        },
        $parent_container: $("#playground-settings").expectOne(),
        init_sort: "pygments_language_alphabetic",
        sort_fields: {
            ...ListWidget.generic_sort_functions("alphabetic", [
                "pygments_language",
                "name",
                "url_template",
            ]),
        },
        $simplebar_container: $("#playground-settings .progressive-table-wrapper"),
    });
}

export function set_up(): void {
    build_page();
    maybe_disable_widgets();
}

function build_page(): void {
    meta.loaded = true;
    populate_playgrounds(realm.realm_playgrounds);
    $(".admin_playgrounds_table").on("click", ".delete", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const $button = $(this);
        const url =
            "/json/realm/playgrounds/" +
            encodeURIComponent($button.closest("tr").attr("data-playground-id")!);
        const html_body = render_confirm_delete_playground();

        confirm_dialog.launch({
            html_heading: $t_html({defaultMessage: "Delete code playground?"}),
            html_body,
            id: "confirm_delete_code_playgrounds_modal",
            on_click() {
                dialog_widget.submit_api_request(channel.del, url, {});
            },
            loading_spinner: true,
        });
    });

    $(".organization form.admin-playground-form")
        .off("submit")
        .on("submit", (e) => {
            e.preventDefault();
            e.stopPropagation();
            const $playground_status = $("#admin-playground-status");
            const $add_playground_button = $(".new-playground-form button");
            $add_playground_button.prop("disabled", true);
            $playground_status.hide();
            const data = {
                name: $("#playground_name").val(),
                pygments_language: $("#playground_pygments_language").val(),
                url_template: $("#playground_url_template").val(),
            };
            void channel.post({
                url: "/json/realm/playgrounds",
                data,
                success() {
                    $("#playground_pygments_language").val("");
                    $("#playground_name").val("");
                    $("#playground_url_template").val("");
                    $add_playground_button.prop("disabled", false);
                    ui_report.success(
                        $t_html({defaultMessage: "Custom playground added!"}),
                        $playground_status,
                        3000,
                    );
                    // FIXME: One thing to note here is that the "view code in playground"
                    // option for an already rendered code block (tagged with this newly added
                    // language) would not be visible without a re-render. To fix this, we should
                    // probably do some extraction in `rendered_markdown.ts` which does a
                    // live-update of the `data-code-language` parameter in code blocks. Or change
                    // how we do the HTML in the frontend so that the icon labels/behavior are
                    // computed dynamically when you hover over the message based on configured
                    // playgrounds. Since this isn't high priority right now, we can probably
                    // take this up later.
                },
                error(xhr) {
                    $add_playground_button.prop("disabled", false);
                    ui_report.error(
                        $t_html({defaultMessage: "Failed"}),
                        xhr,
                        $playground_status,
                        3000,
                    );
                },
            });
        });

    const $search_pygments_box = $<HTMLInputElement>("input#playground_pygments_language");
    const $alias_suggestion_banner = $("<div>")
        .addClass("playground-alias-suggestion-banner alert")
        .hide();
    $search_pygments_box.closest(".input-group").after($alias_suggestion_banner);
    let language_labels = new Map<string, string>();

    const bootstrap_typeahead_input: TypeaheadInputElement = {
        $element: $search_pygments_box,
        type: "input",
    };

    pygments_typeahead = new Typeahead(bootstrap_typeahead_input, {
        source(query: string): string[] {
            language_labels = realm_playground.get_pygments_typeahead_list_for_settings(query);
            return [...language_labels.keys()];
        },
        helpOnEmptyStrings: true,
        item_html: (item: string): string =>
            render_typeahead_item({primary: language_labels.get(item)}),
        matcher(item: string, query: string): boolean {
            const q = query.trim().toLowerCase();
            return item.toLowerCase().startsWith(q);
        },
        sorter(items: string[], query: string): string[] {
            return bootstrap_typeahead.defaultSorter(items, query);
        },
        updater(item: string): string {
            // Hide suggestion when user selects from typeahead
            $alias_suggestion_banner.hide();
            return item;
        },
    });

    function check_and_show_alias_suggestion(): void {
        const current_value = $search_pygments_box.val()?.toString().trim() ?? "";
        const alias_match = realm_playground.find_language_alias_match(current_value);

        if (alias_match === null) {
            $alias_suggestion_banner.hide();
            return;
        }

        // Don't show suggestion if typeahead is currently shown (user might be selecting)
        if (pygments_typeahead.shown) {
            return;
        }

        // Don't show if the current value already matches the full option key
        if (current_value.toLowerCase() === alias_match.full_option_key.toLowerCase()) {
            $alias_suggestion_banner.hide();
            return;
        }

        const aliases_string = util.format_array_as_list_with_conjunction(
            alias_match.aliases,
            "narrow",
        );
        const button_text = $t(
            {defaultMessage: "Use {pretty_name}"},
            {pretty_name: alias_match.pretty_name},
        );
        // This HTML is sanitized by $t_html, which is safe to use with .html()
        const rendered_message = $t_html(
            {
                defaultMessage:
                    "By the way, you can have this playground apply to {aliases}. Would you like to use <strong>{pretty_name}</strong> instead?",
            },
            {
                aliases: aliases_string,
                pretty_name: alias_match.pretty_name,
            },
        );

        const $message_span = $("<span>").html(rendered_message);
        const $button = $("<button>")
            .attr("type", "button")
            .addClass("button small playground-alias-suggestion-button")
            .text(button_text);

        $button.on("click", () => {
            $search_pygments_box.val(alias_match.full_option_key);
            $search_pygments_box.trigger("input");
            $alias_suggestion_banner.hide();
            // Trigger typeahead to show the selected option
            pygments_typeahead.lookup(false);
        });

        $alias_suggestion_banner
            .empty()
            .append($message_span)
            .append($button)
            .removeClass("alert-error alert-success")
            .addClass("alert-info")
            .show();
    }

    $search_pygments_box.on("input", () => {
        // Debounce to avoid checking on every keystroke while typing
        setTimeout(() => {
            // Hide suggestion if typeahead is currently shown
            if (pygments_typeahead.shown) {
                $alias_suggestion_banner.hide();
            } else {
                check_and_show_alias_suggestion();
            }
        }, 300);
    });

    $search_pygments_box.on("blur", () => {
        // Hide suggestion immediately on blur if typeahead is shown
        if (pygments_typeahead.shown) {
            $alias_suggestion_banner.hide();
        } else {
            // Check one more time on blur if typeahead is not shown
            setTimeout(check_and_show_alias_suggestion, 100);
        }
    });

    $search_pygments_box.on("click", (e) => {
        pygments_typeahead.lookup(false);
        $search_pygments_box.trigger("select");
        e.preventDefault();
        e.stopPropagation();
    });
}
