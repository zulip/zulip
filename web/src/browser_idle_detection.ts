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
        addEventListener: (type: "change", listener: () => void) => void;
    }
    // eslint-disable-next-line @typescript-eslint/consistent-type-definitions
    interface Window {
        IdleDetector?: IdleDetectorConstructor;
    }
}

export function supported(): boolean {
    // This API doesn't have widespread support yet, and probably
    // never will. It is not available in Firefox and Safari.
    return "IdleDetector" in window;
}

// Must be called from a handler in a user gesture (ie, click, keypress etc)
export async function request_permission(): Promise<"granted" | "denied"> {
    if (window.IdleDetector === undefined) {
        return "denied";
    }
    return window.IdleDetector.requestPermission();
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
    try {
        const idle_detector = new window.IdleDetector();
        idle_detector.addEventListener("change", () => {
            if (idle_detector.userState === "idle" || idle_detector.screenState === "locked") {
                on_idle();
            } else {
                on_active();
            }
        });
        // The spec enforces a minimum threshold of 60_000ms; anything
        // lower rejects with a TypeError.
        await idle_detector.start({threshold: idle_timeout});
        return "started";
    } catch (error) {
        if (error instanceof Error) {
            return error;
        }
        return new Error(JSON.stringify(error));
    }
}

export async function on_permission_change(on_granted: () => void): Promise<void> {
    const permission_status = await navigator.permissions.query({
        // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
        name: "idle-detection" as PermissionName,
    });
    if (permission_status.state === "granted") {
        on_granted();
    }
    permission_status.addEventListener("change", () => {
        if (permission_status.state === "granted") {
            on_granted();
        }
    });
}
