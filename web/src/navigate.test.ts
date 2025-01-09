import {up} from "./navigate";
import {is_message_partially_visible} from "./message_scroll_state";
import {scroll_to_message} from "./message_viewport";

describe("navigate.up", () => {
    it("should scroll instead of selecting the next message if the top/bottom of the message is not visible", () => {
        const $message_row = $("<div>");
        spyOn(is_message_partially_visible).and.returnValue(false);
        spyOn(scroll_to_message);

        up();

        expect(scroll_to_message).toHaveBeenCalledWith($message_row, "top");
    });

    it("should handle the case where the currently selected message is of normal height, but the one above it is very tall", () => {
        const $message_row = $("<div>");
        spyOn(is_message_partially_visible).and.returnValue(true);
        spyOn(scroll_to_message);

        up();

        expect(scroll_to_message).not.toHaveBeenCalled();
    });
});

describe("message_scroll_state.is_message_partially_visible", () => {
    it("should return true if a message is partially visible in the viewport", () => {
        const $message_row = $("<div>");
        spyOn($message_row, "get_offset_to_window").and.returnValue({top: 100, bottom: 200});
        spyOn(message_viewport, "message_viewport_info").and.returnValue({
            visible_top: 50,
            visible_bottom: 150,
        });

        const result = is_message_partially_visible($message_row);

        expect(result).toBe(true);
    });

    it("should return false if a message is not visible in the viewport", () => {
        const $message_row = $("<div>");
        spyOn($message_row, "get_offset_to_window").and.returnValue({top: 200, bottom: 300});
        spyOn(message_viewport, "message_viewport_info").and.returnValue({
            visible_top: 50,
            visible_bottom: 150,
        });

        const result = is_message_partially_visible($message_row);

        expect(result).toBe(false);
    });
});

describe("message_viewport.scroll_to_message", () => {
    it("should scroll to the top of a message in the viewport", () => {
        const $message_row = $("<div>");
        spyOn($message_row, "get_offset_to_window").and.returnValue({top: 100});
        spyOn($message_row, "outerHeight").and.returnValue(50);
        spyOn(message_viewport, "message_viewport_info").and.returnValue({
            visible_top: 50,
            visible_bottom: 150,
            visible_height: 100,
        });
        spyOn(message_viewport, "set_message_position");

        scroll_to_message($message_row, "top");

        expect(message_viewport.set_message_position).toHaveBeenCalledWith(100, 50, {
            visible_top: 50,
            visible_bottom: 150,
            visible_height: 100,
        }, 0);
    });

    it("should scroll to the bottom of a message in the viewport", () => {
        const $message_row = $("<div>");
        spyOn($message_row, "get_offset_to_window").and.returnValue({top: 100});
        spyOn($message_row, "outerHeight").and.returnValue(50);
        spyOn(message_viewport, "message_viewport_info").and.returnValue({
            visible_top: 50,
            visible_bottom: 150,
            visible_height: 100,
        });
        spyOn(message_viewport, "set_message_position");

        scroll_to_message($message_row, "bottom");

        expect(message_viewport.set_message_position).toHaveBeenCalledWith(100, 50, {
            visible_top: 50,
            visible_bottom: 150,
            visible_height: 100,
        }, 1);
    });
});
