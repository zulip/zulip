import * as blueslip from "./blueslip.ts";

declare global {
    // eslint-disable-next-line @typescript-eslint/consistent-type-definitions
    interface Window {
        IdleDetector: {
            requestPermission: () => Promise<"granted" | "rejected">;
            new (): {
                start: (options: {threshold: number}) => Promise<void>;
                userState: "active" | "idle";
                screenState: "locked" | "unlocked";
                addEventListener: (type: "change", listener: () => void) => void;
            };
        };
    }
}

export async function init_idle_detector_chromium({
    idle_timeout,
    on_idle,
    on_active,
}: {
    idle_timeout: number;
    on_idle: () => void;
    on_active: () => void;
}): Promise<boolean> {
    if (!("IdleDetector" in window)) {
        // This API doesn't have widespread support yet, and probably
        // never will. It is not available in Firefox and Safari.
        return false;
    }
    if ((await window.IdleDetector.requestPermission()) !== "granted") {
        blueslip.warn("Permission to use IdleDetector API denied.");
        return false;
    }
    try {
        const idleDetector = new window.IdleDetector();
        idleDetector.addEventListener("change", () => {
            const userState = idleDetector.userState;
            if (userState === "idle") {
                on_idle();
            } else {
                on_active();
            }
        });

        await idleDetector.start({
            threshold: idle_timeout,
        });
        blueslip.info("IdleDetector started");
        return true;
    } catch (error) {
        if (
            typeof error === "object" &&
            error !== null &&
            "message" in error &&
            typeof error.message === "string"
        ) {
            blueslip.error(error.message);
        } else {
            blueslip.error(JSON.stringify(error));
        }
    }
    return false;
}
