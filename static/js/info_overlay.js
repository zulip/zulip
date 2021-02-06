import * as common from "./common";
import * as components from "./components";
import * as hashchange from "./hashchange";
import * as keydown_util from "./keydown_util";
import * as markdown from "./markdown";
import * as overlays from "./overlays";
import * as popovers from "./popovers";
import * as rendered_markdown from "./rendered_markdown";
import * as ui from "./ui";

// Make it explicit that our toggler is undefined until
// set_up_toggler is called.
export let toggler;

function render_markdown () {
    $.each($("#markdown-instructions .apply_markdown"), (id, element) => {
        const rendering_object = {
            raw_content: element.textContent,
        };
        markdown.apply_markdown(rendering_object);
        const rendered_element = $('<td class="rendered_markdown">');
        rendered_element.html(rendering_object.content);
        rendered_markdown.update_elements(rendered_element);
        rendered_element.insertAfter(element);
    });
};

export function set_up_toggler() {
    render_markdown();
    const opts = {
        selected: 0,
        child_wants_focus: true,
        values: [
            {label: i18n.t("Keyboard shortcuts"), key: "keyboard-shortcuts"},
            {label: i18n.t("Message formatting"), key: "message-formatting"},
            {label: i18n.t("Search operators"), key: "search-operators"},
        ],
        callback(name, key) {
            $(".overlay-modal").hide();
            $(`#${CSS.escape(key)}`).show();
            ui.get_scroll_element($(`#${CSS.escape(key)}`).find(".modal-body")).trigger("focus");
        },
    };

    toggler = components.toggle(opts);
    const elem = toggler.get();
    elem.addClass("large allow-overflow");

    const modals = opts.values.map((item) => {
        const key = item.key; // e.g. message-formatting
        const modal = $(`#${CSS.escape(key)}`).find(".modal-body");
        return modal;
    });

    for (const modal of modals) {
        ui.get_scroll_element(modal).prop("tabindex", 0);
        keydown_util.handle({
            elem: modal,
            handlers: {
                left_arrow: toggler.maybe_go_left,
                right_arrow: toggler.maybe_go_right,
            },
        });
    }

    $(".informational-overlays .overlay-tabs").append(elem);

    common.adjust_mac_shortcuts(".hotkeys_table .hotkey kbd");
    common.adjust_mac_shortcuts("#markdown-instructions kbd");
}

export function show(target) {
    if (!toggler) {
        set_up_toggler();
    }

    const overlay = $(".informational-overlays");

    if (!overlay.hasClass("show")) {
        overlays.open_overlay({
            name: "informationalOverlays",
            overlay,
            on_close() {
                hashchange.exit_overlay();
            },
        });
    }

    if (target) {
        toggler.goto(target);
    }
}

export function maybe_show_keyboard_shortcuts() {
    if (overlays.is_active()) {
        return;
    }
    if (popovers.any_active()) {
        return;
    }
    show("keyboard-shortcuts");
}
