import $ from "jquery";
import {z} from "zod";

import * as channel from "./channel";
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
    const msg = xhr ? channel.xhr_error_message(response_html, xhr) : response_html;
    message(msg, status_box, "alert-error", remove_after);
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

export function generic_embed_error(error_html: string, remove_after: number): void {
    const $alert = $("<div>").addClass(["alert", "home-error-bar", "show"]);
    const $exit = $("<div>").addClass("exit");

    $(".alert-box").append($alert.append($exit, $("<div>").addClass("content").html(error_html)));

    if (remove_after !== undefined) {
        setTimeout(() => {
            $alert.fadeOut(400);
        }, remove_after);
    }
}

export function generic_row_button_error(xhr: JQuery.jqXHR, $btn: JQuery): void {
    let parsed;
    if (
        xhr.status >= 400 &&
        xhr.status < 500 &&
        (parsed = z.object({msg: z.string()}).safeParse(xhr.responseJSON)).success
    ) {
        const $error = $("<p>").addClass("text-error").text(parsed.data.msg);
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

export function loading(
    response_html: string,
    $status_box: JQuery,
    successfully_loaded = false,
): void {
    $status_box.find(".alert-content").html(response_html);
    if (!successfully_loaded) {
        $status_box.removeClass(common.status_classes).addClass("alert-loading").stop(true);
    } else {
        $status_box.removeClass(common.status_classes).addClass("alert-success").stop(true);
        setTimeout(() => {
            $status_box.removeClass("show");
        }, 2500);
    }

    $status_box.addClass("show");
}
