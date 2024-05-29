import $ from "jquery";

import render_settings_admin_realm_domains_list from "../templates/settings/admin_realm_domains_list.hbs";
import render_realm_domains_modal from "../templates/settings/realm_domains_modal.hbs";

import * as channel from "./channel";
import * as dialog_widget from "./dialog_widget";
import {$t_html} from "./i18n";
import {realm} from "./state_data";
import * as ui_report from "./ui_report";

type RealmDomain = {
    domain: string;
    allow_subdomains: boolean;
};

export function populate_realm_domains_table(realm_domains: RealmDomain[]): void {
    // Don't populate the table if the realm domains modal isn't open.
    if ($("#realm_domains_modal").length === 0) {
        return;
    }

    const $realm_domains_table_body = $("#realm_domains_table tbody").expectOne();
    $realm_domains_table_body.find("tr").remove();

    for (const realm_domain of realm_domains) {
        $realm_domains_table_body.append(
            $(render_settings_admin_realm_domains_list({realm_domain})),
        );
    }
}

function fade_status_element($elem: JQuery): void {
    setTimeout(() => {
        $elem.fadeOut(500);
    }, 3000);
}

export function setup_realm_domains_modal_handlers(): void {
    $("#realm_domains_table").on("click", ".delete_realm_domain", function () {
        const domain = $(this).parents("tr").find(".domain").text();
        const url = "/json/realm/domains/" + domain;
        const $realm_domains_info = $(".realm_domains_info");

        void channel.del({
            url,
            success() {
                ui_report.success(
                    $t_html({defaultMessage: "Deleted successfully!"}),
                    $realm_domains_info,
                );
                fade_status_element($realm_domains_info);
            },
            error(xhr) {
                ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $realm_domains_info);
                fade_status_element($realm_domains_info);
            },
        });
    });

    $("#realm_domains_table").on(
        "change",
        "input.allow-subdomains",
        function (this: HTMLInputElement, e) {
            e.stopPropagation();
            const $realm_domains_info = $(".realm_domains_info");
            const domain = $(this).parents("tr").find(".domain").text();
            const allow_subdomains = this.checked;
            const url = "/json/realm/domains/" + domain;
            const data = {
                allow_subdomains: JSON.stringify(allow_subdomains),
            };

            void channel.patch({
                url,
                data,
                success() {
                    if (allow_subdomains) {
                        ui_report.success(
                            $t_html(
                                {
                                    defaultMessage:
                                        "Update successful: Subdomains allowed for {domain}",
                                },
                                {domain},
                            ),
                            $realm_domains_info,
                        );
                    } else {
                        ui_report.success(
                            $t_html(
                                {
                                    defaultMessage:
                                        "Update successful: Subdomains no longer allowed for {domain}",
                                },
                                {domain},
                            ),
                            $realm_domains_info,
                        );
                    }
                    fade_status_element($realm_domains_info);
                },
                error(xhr) {
                    ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $realm_domains_info);
                    fade_status_element($realm_domains_info);
                },
            });
        },
    );

    $("#submit-add-realm-domain").on("click", () => {
        const $realm_domains_info = $(".realm_domains_info");
        const $widget = $("#add-realm-domain-widget");
        const domain = $widget.find(".new-realm-domain").val();
        const allow_subdomains = $widget.find<HTMLInputElement>(
            "input.new-realm-domain-allow-subdomains",
        )[0].checked;
        const data = {
            domain,
            allow_subdomains: JSON.stringify(allow_subdomains),
        };

        void channel.post({
            url: "/json/realm/domains",
            data,
            success() {
                $("#add-realm-domain-widget .new-realm-domain").val("");
                $("#add-realm-domain-widget .new-realm-domain-allow-subdomains").prop(
                    "checked",
                    false,
                );
                ui_report.success(
                    $t_html({defaultMessage: "Added successfully!"}),
                    $realm_domains_info,
                );
                fade_status_element($realm_domains_info);
            },
            error(xhr) {
                ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $realm_domains_info);
                fade_status_element($realm_domains_info);
            },
        });
    });
}

export function show_realm_domains_modal(): void {
    const realm_domains_table_body = render_realm_domains_modal();

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Allowed domains"}),
        html_body: realm_domains_table_body,
        html_submit_button: $t_html({defaultMessage: "Close"}),
        id: "realm_domains_modal",
        on_click() {
            // This modal has no submit button.
        },
        close_on_submit: true,
        focus_submit_on_open: true,
        single_footer_button: true,
        post_render() {
            setup_realm_domains_modal_handlers();
            populate_realm_domains_table(realm.realm_domains);
        },
    });
}
