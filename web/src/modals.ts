import $ from "jquery";
import Micromodal from "micromodal";
import assert from "minimalistic-assert";

import * as blueslip from "./blueslip.ts";
import * as overlay_util from "./overlay_util.ts";
import * as overlays from "./overlays.ts";

type Hook = () => void;

export type ModalConfig = {
    autoremove?: boolean;
    on_show?: () => void;
    on_shown?: (() => void) | undefined;
    on_hide?: (() => void) | undefined;
    on_hidden?: (() => void) | undefined;
};

const pre_open_hooks: Hook[] = [];
const pre_close_hooks: Hook[] = [];

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

export function any_active_or_animating(): boolean {
    const $active_modal = $(".micromodal");
    return $active_modal.hasClass("modal--open") || $active_modal.hasClass("modal--opening");
}

export function any_active(): boolean {
    return $(".micromodal").hasClass("modal--open");
}

export function active_modal(): string | undefined {
    if (!any_active()) {
        blueslip.error("Programming error — Called active_modal when there is no modal open");
        return undefined;
    }

    const $micromodal = $(".micromodal.modal--open");
    return `#${CSS.escape($micromodal.attr("id")!)}`;
}

export function is_active(modal_id: string): boolean {
    const $micromodal = $(".micromodal.modal--open");
    return $micromodal.attr("id") === modal_id;
}

// If conf.autoremove is true, the modal element will be removed from the DOM
// once the modal is hidden.
// conf also accepts the following optional properties:
// on_show: Callback to run when the modal is triggered to show.
// on_shown: Callback to run when the modal is shown.
// on_hide: Callback to run when the modal is triggered to hide.
// on_hidden: Callback to run when the modal is hidden.
export function open(
    modal_id: string,
    conf: ModalConfig & {recursive_call_count?: number} = {},
): void {
    if (modal_id === undefined) {
        blueslip.error("Undefined id was passed into open");
        return;
    }

    // Don't accept hash-based selector to enforce modals to have unique ids and
    // since micromodal doesn't accept hash based selectors.
    if (modal_id.startsWith("#")) {
        blueslip.error("hash-based selector passed in to open", {modal_id});
        return;
    }

    if (any_active()) {
        /*
          Our modal system doesn't directly support opening a modal
          when one is already open, because the `any_active` CSS
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

        close_active();
        setTimeout(() => {
            open(modal_id, conf);
        }, 10);
        return;
    }

    blueslip.debug("open modal: " + modal_id);

    // Micromodal gets elements using the getElementById DOM function
    // which doesn't require the hash. We add it manually here.
    const id_selector = `#${CSS.escape(modal_id)}`;
    const $micromodal = $(id_selector);

    $micromodal.find(".modal__container").on("animationend", (event) => {
        assert(event.originalEvent instanceof AnimationEvent);
        const animation_name = event.originalEvent.animationName;
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
        if (!$(e.target).is(".modal__overlay")) {
            return;
        }

        if ($(e.target).hasClass("ignore-overlay-click")) {
            return;
        }

        /* Micromodal's data-micromodal-close feature doesn't check for
           range selections; this means dragging a selection of text in an
           input inside the modal too far will weirdly close the modal.
           See https://github.com/ghosh/Micromodal/issues/505.
           Work around this with our own implementation. */
        if (document.getSelection()?.type === "Range") {
            return;
        }
        close(modal_id);
    });

    function on_show_callback(): void {
        if (conf.on_show) {
            conf.on_show();
        }
        // We avoid toggling scrolling when opening a modal over an active overlay.
        // This prevents a subtle UI shift, as reported in
        // https://chat.zulip.org/#narrow/channel/9-issues/topic/A.20little.20right.20shift.20can.20be.20observed.20when.20confirm.20dialog.20ope/near/2026160
        // There is no need to enable or disable the scrolling when modal is
        // opened because it is already handled while opening and closing the overlay.
        if (!overlays.any_active()) {
            overlay_util.disable_scrolling();
        }
        call_hooks(pre_open_hooks);
    }

    function on_close_callback(): void {
        if (conf.on_hide) {
            conf.on_hide();
        }
        // Since we are disabling scroll only when the modal is not
        // opened over an overlay, we will enable it in that way only.
        if (!overlays.any_active()) {
            overlay_util.enable_scrolling();
        }
        call_hooks(pre_close_hooks);
    }

    Micromodal.show(modal_id, {
        disableFocus: true,
        openClass: "modal--opening",
        onShow: on_show_callback,
        onClose: on_close_callback,
    });
}

// `conf` is an object with the following optional properties:
// * on_hidden: Callback to run when the modal finishes hiding.
export function close(modal_id: string, conf: Pick<ModalConfig, "on_hidden"> = {}): void {
    if (modal_id === undefined) {
        blueslip.error("Undefined id was passed into close");
        return;
    }

    if (!any_active()) {
        blueslip.warn("close_active() called without checking any_active()");
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
    // overlays.open.  However, we offer this alternative
    // mechanism as a convenience for hooks only known when
    // closing the modal.
    $micromodal.find(".modal__container").on("animationend", (event) => {
        assert(event.originalEvent instanceof AnimationEvent);
        const animation_name = event.originalEvent.animationName;
        if (animation_name === "mmfadeOut" && conf.on_hidden) {
            conf.on_hidden();
        }
    });

    Micromodal.close(modal_id);
}

export function close_if_open(modal_id: string): void {
    if (modal_id === undefined) {
        blueslip.error("Undefined id was passed into close_if_open");
        return;
    }

    if (!any_active()) {
        return;
    }

    const $micromodal = $(".micromodal.modal--open");
    const active_modal_id = CSS.escape(CSS.escape($micromodal.attr("id") ?? ""));
    if (active_modal_id === CSS.escape(modal_id)) {
        Micromodal.close(CSS.escape($micromodal.attr("id") ?? ""));
    } else {
        blueslip.info(
            `${active_modal_id} is the currently active modal and ${modal_id} is already closed.`,
        );
    }
}

export function close_active(): void {
    if (!any_active()) {
        blueslip.warn("close_active() called without checking any_active()");
        return;
    }

    const $micromodal = $(".micromodal.modal--open");
    Micromodal.close(CSS.escape($micromodal.attr("id") ?? ""));
}

export function close_active_if_any(): void {
    if (any_active()) {
        close_active();
    }
}
