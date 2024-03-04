import crypto from "node:crypto";

import bodyParser from "@koa/bodyparser";
import katex from "katex";
import Koa from "koa";

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

app.use((ctx, _next) => {
    if (ctx.request.method !== "POST" || ctx.request.path !== "/") {
        ctx.status = 404;
        return;
    }
    if (ctx.request.body === undefined) {
        ctx.status = 400;
        ctx.type = "text/plain";
        ctx.body = "Missing POST body";
        return;
    }
    const given_secret = ctx.request.body.shared_secret;
    if (typeof given_secret !== "string" || !compare_secret(given_secret)) {
        ctx.status = 403;
        ctx.type = "text/plain";
        ctx.body = "Invalid 'shared_secret' argument";
        return;
    }

    const content = ctx.request.body.content;
    const is_display = ctx.request.body.is_display === "true";

    if (typeof content !== "string") {
        ctx.status = 400;
        ctx.type = "text/plain";
        ctx.body = "Invalid 'content' argument";
        return;
    }

    try {
        ctx.body = katex.renderToString(content, {displayMode: is_display});
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
