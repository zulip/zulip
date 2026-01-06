declare global {
    interface Window {
        blueslip: any;
        blueslip_stacktrace_default: any;
    }
}

// Mock stacktrace to prevent "is not a function" crash
const blueslip_stacktrace = () => "Showcase stacktrace placeholder";
window.blueslip_stacktrace_default = blueslip_stacktrace;

// Mock the logger to catch Zulip's internal warnings
window.blueslip = {
    error: (msg: string, details?: unknown) => console.error("Blueslip Error:", msg, details),
    warn: (msg: string) => console.warn("Blueslip Warn:", msg),
    info: (msg: string) => console.log("Blueslip Info:", msg),
    debug: (msg: string) => console.log("Blueslip Debug:", msg),
    exception: (e: Error) => console.error("Blueslip Exception:", e),
};

export default blueslip_stacktrace;