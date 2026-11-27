declare global {
    // eslint-disable-next-line @typescript-eslint/consistent-type-definitions
    interface IdleDetectorConstructor {
        requestPermission: () => Promise<"granted" | "denied">;
        new (): IdleDetector;
    }
    // eslint-disable-next-line @typescript-eslint/consistent-type-definitions
    interface IdleDetector extends EventTarget {
        readonly userState: "active" | "idle" | null;
        readonly screenState: "locked" | "unlocked" | null;
        start: (options?: {threshold: number; signal?: AbortSignal}) => Promise<void>;
        addEventListener: (
            type: "change",
            listener: () => void,
            options?: {signal?: AbortSignal},
        ) => void;
    }
    // eslint-disable-next-line @typescript-eslint/consistent-type-definitions
    interface Window {
        IdleDetector?: IdleDetectorConstructor;
    }
}

export function supported(): boolean {
    return "IdleDetector" in window;
}

export async function request_permission(): Promise<"granted" | "denied"> {
    if (window.IdleDetector === undefined) {
        return "denied";
    }
    return window.IdleDetector.requestPermission();
}

let active_abort_controller: AbortController | undefined;

export function stop(): void {
    active_abort_controller?.abort();
    active_abort_controller = undefined;
}

export async function init({
    idle_timeout,
    on_idle,
    on_active,
}: {
    idle_timeout: number;
    on_idle: () => void;
    on_active: () => void;
}): Promise<"started" | Error> {
    if (window.IdleDetector === undefined) {
        return new Error("IdleDetector not supported");
    }
    stop();
    const abort_controller = new AbortController();
    active_abort_controller = abort_controller;
    try {
        const idle_detector = new window.IdleDetector();
        const report_state = (): void => {
            if (idle_detector.userState === "idle" || idle_detector.screenState === "locked") {
                on_idle();
            } else {
                on_active();
            }
        };
        idle_detector.addEventListener("change", report_state, {signal: abort_controller.signal});
        // The spec rejects a threshold below 60_000ms with a TypeError.
        await idle_detector.start({threshold: idle_timeout, signal: abort_controller.signal});
        // `change` fires only on transitions, so report the state we
        // start in; a page loaded in a background tab has none coming.
        report_state();
        return "started";
    } catch (error) {
        if (error instanceof Error) {
            return error;
        }
        return new Error(JSON.stringify(error));
    }
}

export async function on_permission_change(on_change: (granted: boolean) => void): Promise<void> {
    const permission_status = await navigator.permissions.query({
        // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
        name: "idle-detection" as PermissionName,
    });
    on_change(permission_status.state === "granted");
    permission_status.addEventListener("change", () => {
        on_change(permission_status.state === "granted");
    });
}
