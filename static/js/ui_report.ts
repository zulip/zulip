import $ from "jquery";
import _ from "lodash";

import * as common from "./common";
import {$t} from "./i18n";

/* Arguments used in the report_* functions are,
   response- response that we want to display
   status_box- element being used to display the response
   cls- class that we want to add/remove to/from the status_box
*/

export function message(
    response_html: string,
    $status_box: JQuery,
    cls = "alert",
    remove_after?: number,
): void {
    // Note we use html() below, since we can rely on our callers escaping HTML
    // via $t_html when interpolating data.
    $status_box
        .removeClass(common.status_classes)
        .addClass(cls)
        .html(response_html)
        .stop(true)
        .fadeTo(0, 1);
    if (remove_after !== undefined) {
        setTimeout(() => {
            $status_box.fadeOut(400);
        }, remove_after);
    }
    $status_box.addClass("show");
}

export function error(
    response_html: string,
    xhr: JQuery.jqXHR | undefined,
    status_box: JQuery,
    remove_after?: number,
): void {
    if (xhr && xhr.status >= 400 && xhr.status < 500) {
        // Only display the error response for 4XX, where we've crafted
        // a nice response.
        const server_response_html = _.escape(JSON.parse(xhr.responseText).msg);
        if (response_html) {
            response_html += ": " + server_response_html;
        } else {
            response_html = server_response_html;
        }
    }

    message(response_html, status_box, "alert-error", remove_after);
}

export function client_error(
    response_html: string,
    status_box: JQuery,
    remove_after?: number,
): void {
    message(response_html, status_box, "alert-error", remove_after);
}

export function success(response_html: string, $status_box: JQuery, remove_after?: number): void {
    message(response_html, $status_box, "alert-success", remove_after);
}

export function generic_embed_error(error_html: string): void {
    const $alert = $("<div>", {class: "alert home-error-bar show"});
    const $exit = $("<div>", {class: "exit"});

    $(".alert-box").append($alert.append($exit, $("<div>", {class: "content"}).html(error_html)));
}

export function generic_row_button_error(xhr: JQuery.jqXHR, $btn: JQuery): void {
    if (xhr.status >= 400 && xhr.status < 500) {
        const $error = $("<p>").addClass("text-error").text(JSON.parse(xhr.responseText).msg);
        $btn.closest("td").empty().append($error);
    } else {
        $btn.text($t({defaultMessage: "Failed!"}));
    }
}

export function hide_error($target: JQuery): void {
    $target.addClass("fade-out");
    setTimeout(() => {
        $target.removeClass("show fade-out");
    }, 300);
}

export function show_error($target: JQuery): void {
    $target.addClass("show");
}
