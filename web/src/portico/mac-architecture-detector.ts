import * as blueslip from "../blueslip.ts";

type UADataValues = {
    [key: string]: string | undefined;
    platform: string;
    architecture?: string;
    bitness?: string;
};

type NavigatorUAData = {
    platform: string;
    getHighEntropyValues: (hints: string[]) => Promise<UADataValues>;
};

declare global {

    interface Navigator {
        userAgentData?: NavigatorUAData;
    }

}

export type ArchitectureInfo = {
    isAppleSilicon: boolean | null;
    confidence: "high" | "low" | "unknown";
};
export class MacArchitectureDetector {
    private static _instance: MacArchitectureDetector | null = null;
    private cached: ArchitectureInfo | null = null;

    private constructor() { void 0; }

    static getInstance(): MacArchitectureDetector {
        MacArchitectureDetector._instance ??= new MacArchitectureDetector();
        return MacArchitectureDetector._instance;
    }

    static __resetForTests(): void {
        MacArchitectureDetector._instance = null;
    }

    async detectArchitecture(): Promise<ArchitectureInfo> {
        if (this.cached) {
            blueslip.debug("MacArch: cached", this.cached);
            return this.cached;
        }

        if (typeof window === "undefined" || typeof document === "undefined" || typeof navigator === "undefined") {
            blueslip.debug("MacArch: non-browser environment");
            this.cached = { isAppleSilicon: null, confidence: "unknown" };
            return this.cached;
        }

        const ua = navigator.userAgent || "";
        if (!/mac/i.test(ua)) {
            this.cached = { isAppleSilicon: null, confidence: "unknown" };
            return this.cached;
        }

        try {
            const uad = navigator.userAgentData;
            if (uad && typeof uad.getHighEntropyValues === "function") {
                const hints = await uad.getHighEntropyValues(["platform", "architecture", "bitness"]);
                blueslip.debug("MacArch: userAgentData hints", hints);
                const platform = hints.platform ?? "";
                if (/mac/i.test(platform)) {
                    const arch = (hints.architecture ?? hints.bitness ?? "").toLowerCase();
                    
                    if (arch.includes("arm") || arch.includes("aarch64") || arch.includes("arm64")) {
                        this.cached = { isAppleSilicon: true, confidence: "high" };
                        return this.cached;
                    }
                    if (arch.includes("x86") || arch.includes("x64") || arch.includes("amd64") || arch.includes("intel")) {
                        this.cached = { isAppleSilicon: false, confidence: "high" };
                        return this.cached;
                    }
                }
            }
        } catch (error) {
            blueslip.debug("MacArch: userAgentData failure", { error: String(error) });
        }

        const lowerUA = ua.toLowerCase();
        if (lowerUA.includes("arm64") || lowerUA.includes("aarch64") || lowerUA.includes("apple silicon")) {
            this.cached = { isAppleSilicon: true, confidence: "low" };
            return this.cached;
        }
        if (lowerUA.includes("x86_64") || lowerUA.includes("intel") || lowerUA.includes("x86")) {
            this.cached = { isAppleSilicon: false, confidence: "low" };
            return this.cached;
        }

        const webgl = this.detectViaWebGL();
        if (webgl) {
            this.cached = webgl;
            return this.cached;
        }

        this.cached = { isAppleSilicon: null, confidence: "unknown" };
        return this.cached;
    }

    getArchitectureName(info: ArchitectureInfo): string {
        if (info.isAppleSilicon === true) {
            return "Apple Silicon";
        }
        if (info.isAppleSilicon === false) {
            return "Intel";
        }
        return "Unknown";
    }

    clearCache(): void {
        this.cached = null;
    }

    private detectViaWebGL(): ArchitectureInfo | null {
        try {
            const canvas = document.createElement("canvas");
            const gl = canvas.getContext("webgl") ?? canvas.getContext("experimental-webgl");
            // Narrow using `instanceof` to avoid unsafe `any` casts and type assertions.
            if (!(gl instanceof WebGLRenderingContext)) {
                return null;
            }

            // standard parameters should be available in WebGLRenderingContext
            let rendererRaw = "";
            let vendorRaw = "";

            try {
                rendererRaw = String(gl.getParameter(gl.RENDERER) ?? "");
                vendorRaw = String(gl.getParameter(gl.VENDOR) ?? "");
            } catch (error) {
                blueslip.debug("MacArch: webgl getParameter blocked", { error: String(error) });
                return null;
            }

            const combined = (rendererRaw + " " + vendorRaw).toLowerCase();

            if (combined.includes("apple") || combined.includes("m1") || combined.includes("m2") || combined.includes("m3") || combined.includes("apple gpu")) {
                return { isAppleSilicon: true, confidence: "low" };
            }
            if (combined.includes("intel") || combined.includes("iris") || combined.includes("hd graphics") || combined.includes("uhd") || combined.includes("radeon")) {
                return { isAppleSilicon: false, confidence: "low" };
            }

            return null;
        } catch (error) {
            blueslip.debug("MacArch: webgl error", { error: String(error) });
            return null;
        }
    }
}

export default MacArchitectureDetector;