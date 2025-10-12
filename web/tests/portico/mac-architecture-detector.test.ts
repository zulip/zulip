/// <reference types="jest" />
/* eslint-env jest */
import MacArchitectureDetector from '../../src/portico/mac-architecture-detector';

describe('MacArchitectureDetector', () => {
    beforeEach(() => {
        // Clear singleton cache via test helper
        // Avoid optional chaining call syntax for test runner parsing compatibility.
        const resetFn = (MacArchitectureDetector as any).__resetForTests;
        if (typeof resetFn === 'function') {
            resetFn();
        }
    });

    test('singleton returns same instance', () => {
        const a = MacArchitectureDetector.getInstance();
        const b = MacArchitectureDetector.getInstance();
        expect(a).toBe(b);
    });

    test('non-mac UA returns unknown', async () => {
        Object.defineProperty(window.navigator, 'userAgent', {
            configurable: true,
            value: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        });
        const detector = MacArchitectureDetector.getInstance();
        const res = await detector.detectArchitecture();
        expect(res.isAppleSilicon).toBeNull();
        expect(res.confidence).toBe('unknown');
    });

    test('UA arm64 detection', async () => {
        Object.defineProperty(window.navigator, 'userAgent', {
            configurable: true,
            value: 'Mozilla/5.0 (Macintosh; ARM64) AppleWebKit',
        });
        const detector = MacArchitectureDetector.getInstance();
        const res = await detector.detectArchitecture();
        expect(res.isAppleSilicon).toBe(true);
    });

    test('UA intel detection', async () => {
        Object.defineProperty(window.navigator, 'userAgent', {
            configurable: true,
            value: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit',
        });
        const detector = MacArchitectureDetector.getInstance();
        const res = await detector.detectArchitecture();
        expect(res.isAppleSilicon).toBe(false);
    });

    describe('userAgentData detection', () => {
        beforeEach(() => {
            // ensure no leftover userAgentData
            // @ts-ignore
            delete (navigator as any).userAgentData;
        });

        test('high confidence Apple Silicon via UA hints', async () => {
            const mockUserAgentData = {
                platform: 'macOS',
                getHighEntropyValues: jest.fn().mockResolvedValue({
                    platform: 'macOS',
                    architecture: 'arm',
                    bitness: '64',
                }),
            } as any;

            Object.defineProperty(navigator, 'userAgentData', {
                configurable: true,
                value: mockUserAgentData,
            });

            (MacArchitectureDetector as typeof MacArchitectureDetector).__resetForTests?.();
            const detector = MacArchitectureDetector.getInstance();
            const result = await detector.detectArchitecture();
            expect(result.isAppleSilicon).toBe(true);
            expect(result.confidence).toBe('high');
        });

        test('high confidence Intel via UA hints', async () => {
            const mockUserAgentData = {
                platform: 'macOS',
                getHighEntropyValues: jest.fn().mockResolvedValue({
                    platform: 'macOS',
                    architecture: 'x86',
                    bitness: '64',
                }),
            } as any;

            Object.defineProperty(navigator, 'userAgentData', {
                configurable: true,
                value: mockUserAgentData,
            });

            (MacArchitectureDetector as typeof MacArchitectureDetector).__resetForTests?.();
            const detector = MacArchitectureDetector.getInstance();
            const result = await detector.detectArchitecture();
            expect(result.isAppleSilicon).toBe(false);
            expect(result.confidence).toBe('high');
        });
    });

    describe('WebGL fallback', () => {
        beforeEach(() => {
            (MacArchitectureDetector as typeof MacArchitectureDetector).__resetForTests?.();
            // ensure no leftover userAgentData from previous tests
            // @ts-ignore - test environment modification
            delete (navigator as any).userAgentData;
        });

        test('detects Apple Silicon via WebGL renderer', async () => {
            // Use a neutral Mac userAgent without architecture hints so the detector
            // falls through to the WebGL fallback path.
            Object.defineProperty(navigator, 'userAgent', {
                configurable: true,
                value: 'Mozilla/5.0 (Macintosh)',
            });

            const mockGL: any = {
                getParameter: jest.fn((_param: any) => {
                    // return renderer string for RENDERER
                    return 'Apple M1 GPU';
                }),
                getExtension: jest.fn().mockReturnValue(null),
            };

            // Ensure a test-side WebGLRenderingContext exists so `instanceof` checks pass.
            // jsdom may not provide WebGLRenderingContext in the test environment.
            if ((global as any).WebGLRenderingContext === undefined) {
                // create a minimal constructor for instanceof checks
                (global as any).WebGLRenderingContext = function WebGLRenderingContext() {};
            }
            // Make our mock appear as an instance of WebGLRenderingContext
            Object.setPrototypeOf(mockGL, (global as any).WebGLRenderingContext.prototype);

            // @ts-ignore
            HTMLCanvasElement.prototype.getContext = jest.fn().mockReturnValue(mockGL);

            const detector = MacArchitectureDetector.getInstance();
            const result = await detector.detectArchitecture();

            expect(result.isAppleSilicon).toBe(true);
            expect(result.confidence).toBe('low');
        });
    });

    describe('caching behavior', () => {
        beforeEach(() => {
            (MacArchitectureDetector as typeof MacArchitectureDetector).__resetForTests?.();
        });

        test('returns cached result on second call', async () => {
            Object.defineProperty(navigator, 'userAgent', {
                configurable: true,
                value: 'Mozilla/5.0 (Macintosh; ARM64) AppleWebKit',
            });

            const detector = MacArchitectureDetector.getInstance();
            const first = await detector.detectArchitecture();
            const second = await detector.detectArchitecture();

            expect(first).toBe(second);
        });

        test('clearCache forces re-detection', async () => {
            Object.defineProperty(navigator, 'userAgent', {
                configurable: true,
                value: 'Mozilla/5.0 (Macintosh; ARM64) AppleWebKit',
            });

            const detector = MacArchitectureDetector.getInstance();
            const first = await detector.detectArchitecture();
            detector.clearCache();
            const second = await detector.detectArchitecture();

            expect(first).not.toBe(second);
        });
    });
});
