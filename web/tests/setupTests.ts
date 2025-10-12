// Test setup: define globals used at runtime by the web code.
(global as any).DEVELOPMENT = false;

// Minimal jQuery stub for code that expects $ to exist during tests.
import jquery from 'jquery';
(global as any).$ = jquery;
