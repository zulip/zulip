// Mobile keyboard handler for positioning compose box above on-screen keyboard
// Uses visualViewport API to detect keyboard height and adjust compose position

let keyboard_offset = 0;
let resize_observer: ResizeObserver | null = null;

// Callbacks registered by other modules to react to keyboard offset changes
const offset_change_callbacks: ((offset: number) => void)[] = [];

function update_compose_position(): void {
    const compose_element = document.querySelector<HTMLElement>("#compose");
    if (!compose_element) {
        return;
    }

    compose_element.style.setProperty("--keyboard-offset", `${keyboard_offset}px`);
}

function notify_offset_change(): void {
    for (const callback of offset_change_callbacks) {
        callback(keyboard_offset);
    }
}

function calculate_keyboard_offset(): number {
    if (!window.visualViewport) {
        return 0;
    }

    const viewport_height = window.visualViewport.height;
    const viewport_offset_top = window.visualViewport.offsetTop;
    // Use clientHeight (Layout Height) instead of innerHeight (Visible Height)
    // to ensure consistency with visualViewport properties which are relative to layout
    const window_height = document.documentElement.clientHeight;

    // Keyboard height = window height - (viewport height + viewport offset)
    // We subtract viewport_offset_top to prevent the compose box from scrolling with the chat.
    // This pins the compose box to the bottom of the visible area (visual viewport).
    const offset = Math.max(0, window_height - (viewport_height + viewport_offset_top));

    // Only consider keyboard present if offset is significant (> 100px)
    // This helps filter out address bar changes and other small viewport adjustments
    return offset > 100 ? offset : 0;
}

function calculate_and_update_offset(): void {
    const new_keyboard_offset = calculate_keyboard_offset();

    if (new_keyboard_offset !== keyboard_offset) {
        keyboard_offset = new_keyboard_offset;
        update_compose_position();
        notify_offset_change();
    }
}

function handle_resize(): void {
    calculate_and_update_offset();
}

function handle_scroll(): void {
    if (window.visualViewport) {
        calculate_and_update_offset();
    }
}

function handle_focus(): void {
    // When an input is focused, keyboard may appear
    // Poll for changes over the next 1 second to catch keyboard animation
    let poll_count = 0;
    const poll = (): void => {
        calculate_and_update_offset();
        poll_count += 1;
        if (poll_count < 10) {
            setTimeout(poll, 100);
        }
    };
    poll();
}

// Public API: Get the current keyboard offset
export function get_keyboard_offset(): number {
    return keyboard_offset;
}

// Public API: Register a callback for when keyboard offset changes
export function on_offset_change(callback: (offset: number) => void): void {
    offset_change_callbacks.push(callback);
}

// Public API: Unregister a callback
export function off_offset_change(callback: (offset: number) => void): void {
    const index = offset_change_callbacks.indexOf(callback);
    if (index !== -1) {
        offset_change_callbacks.splice(index, 1);
    }
}

export function initialize_mobile_keyboard_handler(): void {
    // Listen for visualViewport changes
    if (window.visualViewport) {
        window.visualViewport.addEventListener("resize", handle_resize);
        // Listen to scroll to update position when chat scrolls (prevents compose from moving with chat)
        window.visualViewport.addEventListener("scroll", handle_scroll);
    }

    // Also listen for window resize as fallback
    window.addEventListener("resize", handle_resize);

    // Listen for focus events on inputs within compose
    document.addEventListener("focusin", (event: FocusEvent) => {
        const target = event.target;
        if (target instanceof HTMLElement) {
            const compose = document.querySelector("#compose");
            if (compose?.contains(target)) {
                handle_focus();
            }
        }
    });

    // Use ResizeObserver on body as another fallback
    if (typeof ResizeObserver !== "undefined") {
        resize_observer = new ResizeObserver(() => {
            calculate_and_update_offset();
        });
        resize_observer.observe(document.body);
    }

    // Initial calculation
    calculate_and_update_offset();
}

export function cleanup_mobile_keyboard_handler(): void {
    if (window.visualViewport) {
        window.visualViewport.removeEventListener("resize", handle_resize);
        window.visualViewport.removeEventListener("scroll", handle_scroll);
    }

    window.removeEventListener("resize", handle_resize);

    if (resize_observer) {
        resize_observer.disconnect();
        resize_observer = null;
    }

    keyboard_offset = 0;
    update_compose_position();
}
