declare global {
    // eslint-disable-next-line @typescript-eslint/consistent-type-definitions
    interface Window {
        IdleDetector: {
            requestPermission: () => Promise<"granted" | "denied">;
            new (): {
                start: (options: {threshold: number}) => Promise<void>;
                userState: "active" | "idle";
                screenState: "locked" | "unlocked";
                addEventListener: (type: "change", listener: () => void) => void;
            };
        };
    }
    // eslint-disable-next-line @typescript-eslint/consistent-type-definitions
    interface Permission {
        query: (permission_info: {name: "idle-detection"}) => Promise<{
            state: "granted" | "denied" | "prompt";
            addEventListener: (type: "change", listener: () => void) => void;
        }>;
    }
}

export function supported(): boolean {
    // This API doesn't have widespread support yet, and probably
    // never will. It is not available in Firefox and Safari.
    return "IdleDetector" in window;
}

// Must be called from a handler in a user gesture (ie, click, keypress etc)
export async function request_permission(): Promise<"granted" | "denied"> {
    if (!supported()) {
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
    try {
        const idleDetector = new window.IdleDetector();
        idleDetector.addEventListener("change", () => {
            const userState = idleDetector.userState;
            const screenState = idleDetector.screenState;
            if (userState === "idle" || screenState === "locked") {
                on_idle();
            } else {
                on_active();
            }
        });

        await idleDetector.start({
            threshold: idle_timeout,
        });
        return "started";
    } catch (error) {
        if (error instanceof Error) {
            return error;
        }
        return new Error(JSON.stringify(error));
    }
}

export function on_permission_change(on_granted: () => void): void {
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-ignore
    void navigator.permissions.query({name: "idle-detection"}).then((permissionStatus) => {
        if (permissionStatus.state === "granted") {
            on_granted();
        }
        permissionStatus.addEventListener("change", () => {
            if (permissionStatus.state === "granted") {
                on_granted();
            }
        });
    });
}
