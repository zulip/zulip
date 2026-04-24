import type * as tippy from "tippy.js";

// Watches the reference element's class for changes while a tooltip is
// visible, so the content stays accurate when the element is toggled via
// keyboard (or any other path) without hiding the tooltip first.
const class_observers = new WeakMap<tippy.Instance, MutationObserver>();
export function observe_toggle_class(instance: tippy.Instance, update: () => void): void {
    update();
    const observer = new MutationObserver(update);
    observer.observe(instance.reference, {
        attributes: true,
        attributeFilter: ["class"],
    });
    class_observers.set(instance, observer);
}
export function disconnect_toggle_class(instance: tippy.Instance): void {
    class_observers.get(instance)?.disconnect();
    class_observers.delete(instance);
}
