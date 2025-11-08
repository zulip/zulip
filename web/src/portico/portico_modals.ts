import $ from "jquery";
import Micromodal from "micromodal";
import assert from "minimalistic-assert";

import * as blueslip from "../blueslip.ts";

function is_open(): boolean {
    return $(".micromodal").hasClass("modal--open");
}

function active_modal(): string | undefined {
    if (!is_open()) {
        blueslip.error("Programming error — Called active_modal when there is no modal open");
        return undefined;
    }

    const $micromodal = $(".micromodal.modal--open");
    return `#${CSS.escape($micromodal.attr("id")!)}`;
}

export function close_active(): void {
    if (!is_open()) {
        blueslip.warn("close_active() called without checking is_open()");
        return;
    }

    const $micromodal = $(".micromodal.modal--open");
    Micromodal.close(CSS.escape($micromodal.attr("id") ?? ""));
}

export function open(modal_id: string, recursive_call_count = 0): void {
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

    if (is_open()) {
        /*
          Our modal system doesn't directly support opening a modal
          when one is already open, because the `is_open` CSS
          class doesn't update until Micromodal has finished its
          animations, which can take 100ms or more.

          We can likely fix that, but in the meantime, we should
          handle this situation correctly, by closing the current
          modal, waiting for it to finish closing, and then attempting
          to open the current modal again.
        */
        if (recursive_call_count) {
            recursive_call_count = 1;
        } else {
            recursive_call_count += 1;
        }
        if (recursive_call_count > 50) {
            blueslip.error("Modal incorrectly is still open", {modal_id});
            return;
        }

        close_active();
        setTimeout(() => {
            open(modal_id, recursive_call_count);
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
        } else if (animation_name === "mmfadeOut") {
            $micromodal.removeClass("modal--open");
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
        close(modal_id);
    });

    Micromodal.show(modal_id, {
        disableFocus: true,
        openClass: "modal--opening",
    });
}

export function close(modal_id: string): void {
    if (modal_id === undefined) {
        blueslip.error("Undefined id was passed into close");
        return;
    }

    if (!is_open()) {
        blueslip.warn("close_active() called without checking is_open()");
        return;
    }

    if (active_modal() !== `#${CSS.escape(modal_id)}`) {
        blueslip.error("Trying to close modal when other is open", {modal_id, active_modal});
        return;
    }

    blueslip.debug("close modal: " + modal_id);

    Micromodal.close(modal_id);
}
