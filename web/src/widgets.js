import * as poll_widget from "./poll_widget";
import * as todo_widget from "./todo_widget";
import * as widgetize from "./widgetize";
import * as zform from "./zform";

export const initialize = () => {
    widgetize.widgets.set("poll", poll_widget);
    widgetize.widgets.set("todo", todo_widget);
    widgetize.widgets.set("zform", zform);
};
