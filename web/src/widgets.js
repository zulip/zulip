import * as poll_widget from "./poll_widget.ts";
import * as todo_widget from "./todo_widget.ts";
import * as widgetize from "./widgetize.ts";
import * as zform from "./zform.js";

export function initialize() {
    widgetize.widgets.set("poll", poll_widget);
    widgetize.widgets.set("todo", todo_widget);
    widgetize.widgets.set("zform", zform);
}
