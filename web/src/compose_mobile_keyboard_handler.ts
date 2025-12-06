let keyboard_offset = 0;

function update_compose_position(): void {
    const compose_element = document.querySelector<HTMLElement>("#compose");
    if (!compose_element) {
        return;
    }

    compose_element.style.setProperty("--keyboard-offset", `${keyboard_offset}px`);
}

function handle_viewport_change(): void {
    if (!window.visualViewport) {
        return;
    }

    // Calculate keyboard height
    const viewport_height = window.visualViewport.height;
    const viewport_offset_top = window.visualViewport.offsetTop;
    const window_height = window.innerHeight;

    // Keyboard height = window height - (viewport height + viewport offset)
    const new_keyboard_offset = Math.max(
        0,
        window_height - (viewport_height + viewport_offset_top),
    );

    if (new_keyboard_offset !== keyboard_offset) {
        keyboard_offset = new_keyboard_offset;
        update_compose_position();
    }
}

export function initialize_mobile_keyboard_handler(): void {
    // Only initialize on mobile devices that support visualViewport
    if (!window.visualViewport) {
        return;
    }

    // Listen for viewport changes
    window.visualViewport.addEventListener("resize", handle_viewport_change);
    window.visualViewport.addEventListener("scroll", handle_viewport_change);

    // Initial setup
    handle_viewport_change();
}

export function cleanup_mobile_keyboard_handler(): void {
    if (!window.visualViewport) {
        return;
    }

    window.visualViewport.removeEventListener("resize", handle_viewport_change);
    window.visualViewport.removeEventListener("scroll", handle_viewport_change);

    keyboard_offset = 0;
    update_compose_position();
}
