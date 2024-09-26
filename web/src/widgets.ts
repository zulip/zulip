import * as poll_widget from "./poll_widget";
import * as todo_widget from "./todo_widget";
import * as widgetize from "./widgetize";
const zform: any = require("./zform");
import {WidgetValue} from "./widgetize";

export function initialize(): void {
    widgetize.widgets.set("poll", poll_widget as WidgetValue);
    widgetize.widgets.set("todo", todo_widget as WidgetValue);
    widgetize.widgets.set("zform", zform as WidgetValue);
}
