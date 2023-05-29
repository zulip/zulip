import $ from "jquery";
import Micromodal from "micromodal";

import * as blueslip from "./blueslip";

type Hook = () => void;

type OverlayOptions = {
    name: string;
    $overlay: JQuery;
    on_close: () => void;
};

type Overlay = {
    $element: JQuery;
    close_handler: () => void;
};

export type ModalConfig = {
    autoremove?: boolean;
    on_show?: () => void;
    on_shown?: () => void;
    on_hide?: () => void;
    on_hidden?: () => void;
};

let active_overlay: Overlay | undefined;
let open_overlay_name: string | undefined;

const pre_open_hooks: Hook[] = [];
const pre_close_hooks: Hook[] = [];

function reset_state(): void {
    active_overlay = undefined;
    open_overlay_name = undefined;
}

export function register_pre_open_hook(func: Hook): void {
    pre_open_hooks.push(func);
}

export function register_pre_close_hook(func: Hook): void {
    pre_close_hooks.push(func);
}

function call_hooks(func_list: Hook[]): void {
    for (const element of func_list) {
        element();
    }
}

export function disable_scrolling(): void {
    // Why disable scrolling?
    // Since fixed / absolute positined elements don't capture the scroll event unless
    // they overflow their defined container. Since fixed / absolute elements are not treated
    // as part of the document flow, we cannot capture `scroll` events on them and prevent propagation
    // as event bubbling doesn't work naturally.
    const scrollbar_width = window.innerWidth - document.documentElement.clientWidth;
    $("html").css({"overflow-y": "hidden", "--disabled-scrollbar-width": `${scrollbar_width}px`});
}

function enable_scrolling(): void {
    $("html").css({"overflow-y": "scroll", "--disabled-scrollbar-width": "0px"});
}

export function is_active(): boolean {
    return Boolean(open_overlay_name);
}

export function is_modal_open(): boolean {
    return $(".micromodal").hasClass("modal--open");
}

export function is_overlay_or_modal_open(): boolean {
    return is_active() || is_modal_open();
}

export function info_overlay_open(): boolean {
    return open_overlay_name === "informationalOverlays";
}

export function settings_open(): boolean {
    return open_overlay_name === "settings";
}

export function streams_open(): boolean {
    return open_overlay_name === "subscriptions";
}

export function groups_open(): boolean {
    return open_overlay_name === "group_subscriptions";
}

export function lightbox_open(): boolean {
    return open_overlay_name === "lightbox";
}

export function drafts_open(): boolean {
    return open_overlay_name === "drafts";
}

export function scheduled_messages_open(): boolean {
    return open_overlay_name === "scheduled";
}

export function active_modal(): string | undefined {
    if (!is_modal_open()) {
        blueslip.error("Programming error — Called active_modal when there is no modal open");
        return undefined;
    }

    const $micromodal = $(".micromodal.modal--open");
    return `#${CSS.escape($micromodal.attr("id")!)}`;
}

export function open_overlay(opts: OverlayOptions): void {
    call_hooks(pre_open_hooks);

    if (!opts.name || !opts.$overlay || !opts.on_close) {
        blueslip.error("Programming error in open_overlay");
        return;
    }

    if (active_overlay || open_overlay_name) {
        blueslip.error("Programming error - trying to open overlay before closing other", {
            name: opts.name,
            open_overlay_name,
        });
        return;
    }

    blueslip.debug("open overlay: " + opts.name);

    // Our overlays are kind of crufty...we have an HTML id
    // attribute for them and then a data-overlay attribute for
    // them.  Make sure they match.
    if (opts.$overlay.attr("data-overlay") !== opts.name) {
        blueslip.error("Bad overlay setup for " + opts.name);
        return;
    }

    open_overlay_name = opts.name;
    active_overlay = {
        $element: opts.$overlay,
        close_handler() {
            opts.on_close();
            reset_state();
        },
    };

    disable_scrolling();
    opts.$overlay.addClass("show");
    opts.$overlay.attr("aria-hidden", "false");
    $(".app").attr("aria-hidden", "true");
    $("#navbar-fixed-container").attr("aria-hidden", "true");
}

// If conf.autoremove is true, the modal element will be removed from the DOM
// once the modal is hidden.
// conf also accepts the following optional properties:
// on_show: Callback to run when the modal is triggered to show.
// on_shown: Callback to run when the modal is shown.
// on_hide: Callback to run when the modal is triggered to hide.
// on_hidden: Callback to run when the modal is hidden.
export function open_modal(
    modal_id: string,
    conf: ModalConfig & {recursive_call_count?: number} = {},
): void {
    if (modal_id === undefined) {
        blueslip.error("Undefined id was passed into open_modal");
        return;
    }

    // Don't accept hash-based selector to enforce modals to have unique ids and
    // since micromodal doesn't accept hash based selectors.
    if (modal_id.startsWith("#")) {
        blueslip.error("hash-based selector passed in to open_modal", {modal_id});
        return;
    }

    if (is_modal_open()) {
        /*
          Our modal system doesn't directly support opening a modal
          when one is already open, because the `is_modal_open` CSS
          class doesn't update until Micromodal has finished its
          animations, which can take 100ms or more.

          We can likely fix that, but in the meantime, we should
          handle this situation correctly, by closing the current
          modal, waiting for it to finish closing, and then attempting
          to open the current modal again.
        */
        if (!conf.recursive_call_count) {
            conf.recursive_call_count = 1;
        } else {
            conf.recursive_call_count += 1;
        }
        if (conf.recursive_call_count > 50) {
            blueslip.error("Modal incorrectly is still open", {modal_id});
            return;
        }

        close_active_modal();
        setTimeout(() => {
            open_modal(modal_id, conf);
        }, 10);
        return;
    }

    blueslip.debug("open modal: " + modal_id);

    // Micromodal gets elements using the getElementById DOM function
    // which doesn't require the hash. We add it manually here.
    const id_selector = `#${CSS.escape(modal_id)}`;
    const $micromodal = $(id_selector);

    $micromodal.find(".modal__container").on("animationend", (event) => {
        const animation_name = (event.originalEvent as AnimationEvent).animationName;
        if (animation_name === "mmfadeIn") {
            // Micromodal adds the is-open class before the modal animation
            // is complete, which isn't really helpful since a modal is open after the
            // animation is complete. So, we manually add a class after the
            // animation is complete.
            $micromodal.addClass("modal--open");
            $micromodal.removeClass("modal--opening");

            if (conf.on_shown) {
                conf.on_shown();
            }
        } else if (animation_name === "mmfadeOut") {
            // Call the on_hidden callback after the modal finishes hiding.

            $micromodal.removeClass("modal--open");
            if (conf.autoremove) {
                $micromodal.remove();
            }
            if (conf.on_hidden) {
                conf.on_hidden();
            }
        }
    });

    $micromodal.find(".modal__overlay").on("click", (e) => {
        /* Micromodal's data-micromodal-close feature doesn't check for
           range selections; this means dragging a selection of text in an
           input inside the modal too far will weirdly close the modal.
           See https://github.com/ghosh/Micromodal/issues/505.
           Work around this with our own implementation. */
        if (!$(e.target).is(".modal__overlay")) {
            return;
        }

        if (document.getSelection()?.type === "Range") {
            return;
        }
        close_modal(modal_id);
    });

    function on_show_callback(): void {
        if (conf.on_show) {
            conf.on_show();
        }
        disable_scrolling();
    }

    function on_close_callback(): void {
        if (conf.on_hide) {
            conf.on_hide();
        }
        enable_scrolling();
    }

    Micromodal.show(modal_id, {
        disableFocus: true,
        openClass: "modal--opening",
        onShow: on_show_callback,
        onClose: on_close_callback,
    });
}

export function close_overlay(name: string): void {
    call_hooks(pre_close_hooks);

    if (name !== open_overlay_name) {
        blueslip.error("Trying to close overlay with another open", {name, open_overlay_name});
        return;
    }

    if (name === undefined) {
        blueslip.error("Undefined name was passed into close_overlay");
        return;
    }

    if (active_overlay === undefined) {
        blueslip.error("close_overlay called without checking is_active()");
        return;
    }

    blueslip.debug("close overlay: " + name);
    active_overlay.$element.removeClass("show");

    active_overlay.$element.attr("aria-hidden", "true");
    $(".app").attr("aria-hidden", "false");
    $("#navbar-fixed-container").attr("aria-hidden", "false");

    active_overlay.close_handler();
    enable_scrolling();
}

export function close_active(): void {
    if (!open_overlay_name) {
        blueslip.warn("close_active() called without checking is_active()");
        return;
    }

    close_overlay(open_overlay_name);
}

// `conf` is an object with the following optional properties:
// * on_hidden: Callback to run when the modal finishes hiding.
export function close_modal(modal_id: string, conf: Pick<ModalConfig, "on_hidden"> = {}): void {
    if (modal_id === undefined) {
        blueslip.error("Undefined id was passed into close_modal");
        return;
    }

    if (!is_modal_open()) {
        blueslip.warn("close_active_modal() called without checking is_modal_open()");
        return;
    }

    if (active_modal() !== `#${CSS.escape(modal_id)}`) {
        blueslip.error("Trying to close modal when other is open", {modal_id, active_modal});
        return;
    }

    blueslip.debug("close modal: " + modal_id);

    const id_selector = `#${CSS.escape(modal_id)}`;
    const $micromodal = $(id_selector);

    // On-hidden hooks should typically be registered in
    // overlays.open_modal.  However, we offer this alternative
    // mechanism as a convenience for hooks only known when
    // closing the modal.
    $micromodal.find(".modal__container").on("animationend", (event) => {
        const animation_name = (event.originalEvent as AnimationEvent).animationName;
        if (animation_name === "mmfadeOut" && conf.on_hidden) {
            conf.on_hidden();
        }
    });

    Micromodal.close(modal_id);
}

export function close_modal_if_open(modal_id: string): void {
    if (modal_id === undefined) {
        blueslip.error("Undefined id was passed into close_modal_if_open");
        return;
    }

    if (!is_modal_open()) {
        return;
    }

    const $micromodal = $(".micromodal.modal--open");
    const active_modal_id = CSS.escape(`${CSS.escape($micromodal.attr("id") ?? "")}`);
    if (active_modal_id === `${CSS.escape(modal_id)}`) {
        Micromodal.close(`${CSS.escape($micromodal.attr("id") ?? "")}`);
    } else {
        blueslip.info(
            `${active_modal_id} is the currently active modal and ${modal_id} is already closed.`,
        );
    }
}

export function close_active_modal(): void {
    if (!is_modal_open()) {
        blueslip.warn("close_active_modal() called without checking is_modal_open()");
        return;
    }

    const $micromodal = $(".micromodal.modal--open");
    Micromodal.close(`${CSS.escape($micromodal.attr("id") ?? "")}`);
}

export function close_for_hash_change(): void {
    if (open_overlay_name) {
        close_overlay(open_overlay_name);
    }
}

export function initialize(): void {
    $("body").on("click", "div.overlay, div.overlay .exit", (e) => {
        let $target = $(e.target);

        if (document.getSelection()?.type === "Range") {
            return;
        }

        // if the target is not the div.overlay element, search up the node tree
        // until it is found.
        if ($target.is(".exit, .exit-sign, .overlay-content, .exit span")) {
            $target = $target.closest("[data-overlay]");
        } else if (!$target.is("div.overlay")) {
            // not a valid click target then.
            return;
        }

        if ($target.data("noclose")) {
            // This overlay has been marked explicitly to not be closed.
            return;
        }

        const target_name = $target.attr("data-overlay")!;

        close_overlay(target_name);

        e.preventDefault();
        e.stopPropagation();
    });
}
