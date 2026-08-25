import * as generic_widget from "./generic_widget.ts";
import * as poll_widget from "./poll_widget.ts";
import * as todo_widget from "./todo_widget.ts";
import * as zform from "./zform.ts";

export function initialize(): void {
    generic_widget.widgets.set("poll", poll_widget);
    generic_widget.widgets.set("todo", todo_widget);
    generic_widget.widgets.set("zform", zform);
}
