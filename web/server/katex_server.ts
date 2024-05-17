import crypto from "node:crypto";

import bodyParser from "@koa/bodyparser";
import katex from "katex";
import Koa from "koa";
import Prometheus from "prom-client";

const host = "localhost";
const port = Number(process.argv[2] ?? "9700");
if (!Number.isInteger(port)) {
    throw new TypeError("Invalid port");
}

const shared_secret = process.env.SHARED_SECRET;
if (typeof shared_secret !== "string") {
    console.error("No SHARED_SECRET set!");
    process.exit(1);
}
const compare_secret = (given_secret: string): boolean => {
    try {
        // Throws an exception if the strings are unequal length
        return crypto.timingSafeEqual(
            Buffer.from(shared_secret, "utf8"),
            Buffer.from(given_secret, "utf8"),
        );
    } catch {
        return false;
    }
};

const app = new Koa();
app.use(bodyParser());

Prometheus.collectDefaultMetrics();
const httpRequestDurationSeconds = new Prometheus.Histogram({
    name: "katex_http_request_duration_seconds",
    help: "Duration of HTTP requests in seconds",
    labelNames: ["method", "path", "status"] as const,
    buckets: [
        0.00001, 0.00002, 0.00005, 0.0001, 0.0002, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05,
        0.1,
    ],
});

const httpRequestSizeBytes = new Prometheus.Histogram({
    name: "katex_request_size_bytes",
    help: "Size of successful KaTeX input in bytes",
    labelNames: ["display_mode"] as const,
    buckets: [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000],
});

const httpResponseSizeBytes = new Prometheus.Histogram({
    name: "katex_response_size_bytes",
    help: "Size of successful KaTeX output in bytes",
    labelNames: ["display_mode"] as const,
    buckets: [100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000],
});

app.use(async (ctx, next) => {
    if (ctx.request.method === "GET" && ctx.request.path === "/metrics") {
        ctx.body = await Prometheus.register.metrics();
        return;
    }
    const endTimer = httpRequestDurationSeconds.startTimer();
    await next();
    const {method, path} = ctx.request;
    const {status} = ctx.response;
    httpRequestDurationSeconds.labels({method, path, status: String(status)}).observe(endTimer());
});

app.use((ctx, _next) => {
    if (ctx.request.method !== "POST" || ctx.request.path !== "/") {
        ctx.status = 404;
        return;
    }
    const body: unknown = ctx.request.body;
    if (typeof body !== "object" || body === null) {
        ctx.status = 400;
        ctx.type = "text/plain";
        ctx.body = "Missing POST body";
        return;
    }
    if (
        !("shared_secret" in body) ||
        typeof body.shared_secret !== "string" ||
        !compare_secret(body.shared_secret)
    ) {
        ctx.status = 403;
        ctx.type = "text/plain";
        ctx.body = "Invalid 'shared_secret' argument";
        return;
    }

    const is_display = "is_display" in body && body.is_display === "true";

    if (!("content" in body) || typeof body.content !== "string") {
        ctx.status = 400;
        ctx.type = "text/plain";
        ctx.body = "Invalid 'content' argument";
        return;
    }
    const content = body.content;

    httpRequestSizeBytes.labels(String(is_display)).observe(Buffer.byteLength(content, "utf8"));
    try {
        const output = katex.renderToString(content, {displayMode: is_display});
        ctx.body = output;
        httpResponseSizeBytes.labels(String(is_display)).observe(Buffer.byteLength(output, "utf8"));
    } catch (error) {
        if (error instanceof katex.ParseError) {
            ctx.status = 400;
            ctx.type = "text/plain";
            ctx.body = error.message;
        } else {
            ctx.status = 500;
            console.error(error);
        }
    }
});

app.listen(port, host, () => {
    console.log(`Server started on http://${host}:${port}`);
});
