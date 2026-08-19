// Re-introduce a name that TypeScript 5.7 added and TypeScript 6 removed,
// because livekit-client@2.19.1's bundled .d.ts files still reference it.
type NonSharedUint8Array = Uint8Array<ArrayBuffer>;
