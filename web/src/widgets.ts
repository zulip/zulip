import * as command_invocation_widget from "./command_invocation_widget.ts";
import * as freeform_widget from "./freeform_widget.ts";
import * as interactive_widget from "./interactive_widget.ts";
import * as poll_widget from "./poll_widget.ts";
import * as rich_embed_widget from "./rich_embed_widget.ts";
import * as todo_widget from "./todo_widget.ts";
import * as widgetize from "./widgetize.ts";
import * as zform from "./zform.ts";

export function initialize(): void {
    widgetize.widgets.set("poll", poll_widget);
    widgetize.widgets.set("todo", todo_widget);
    widgetize.widgets.set("zform", zform);
    widgetize.widgets.set("rich_embed", rich_embed_widget);
    widgetize.widgets.set("interactive", interactive_widget);
    widgetize.widgets.set("freeform", freeform_widget);
    widgetize.widgets.set("command_invocation", command_invocation_widget);
}
