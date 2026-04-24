// This function runs a Promise-returning task in the background
// without awaiting it.

// This is useful in node tests, because unawaited tasks that throw
// errors can cause unhandled rejections after tests finish,
// making failures hard to pinpoint. Mocking `run` lets us avoid
// these issues.
export function run_async_function_without_await(task: () => Promise<void>): void {
    void task();
}
