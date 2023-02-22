// This plugin exposes a version of require() to the browser console to assist
// debugging.  It also exposes the list of modules it knows about as the keys
// of the require.ids object.

import path from "path";

import type {ResolveRequest} from "enhanced-resolve";
import type {Chunk, Compiler, WebpackPluginInstance} from "webpack";
import {NormalModule, Template} from "webpack";

export default class DebugRequirePlugin implements WebpackPluginInstance {
    apply(compiler: Compiler): void {
        const resolved = new Map<string, Set<string>>();
        const nameSymbol = Symbol("DebugRequirePluginName");
        type NamedRequest = ResolveRequest & {
            [nameSymbol]?: string;
        };
        let debugRequirePath: string | false = false;

        compiler.resolverFactory.hooks.resolver
            .for("normal")
            .tap("DebugRequirePlugin", (resolver) => {
                resolver.getHook("beforeRawModule").tap("DebugRequirePlugin", (req) => {
                    if (!(nameSymbol in req)) {
                        (req as NamedRequest)[nameSymbol] = req.request;
                    }
                    return undefined!;
                });

                resolver.getHook("beforeRelative").tap("DebugRequirePlugin", (req) => {
                    if (req.path !== false) {
                        const inPath = path.relative(compiler.context, req.path);
                        if (!inPath.startsWith("../") && !(nameSymbol in req)) {
                            (req as NamedRequest)[nameSymbol] = "./" + inPath;
                        }
                    }
                    return undefined!;
                });

                resolver
                    .getHook("beforeResolved")
                    .tap("DebugRequirePlugin", (req: ResolveRequest) => {
                        const name = (req as NamedRequest)[nameSymbol];
                        if (name !== undefined && req.path !== false) {
                            const names = resolved.get(req.path);
                            if (names) {
                                names.add(name);
                            } else {
                                resolved.set(req.path, new Set([name]));
                            }
                        }
                        return undefined!;
                    });
            });

        compiler.hooks.beforeCompile.tapPromise(
            "DebugRequirePlugin",
            async ({normalModuleFactory}) => {
                const resolver = normalModuleFactory.getResolver("normal");
                debugRequirePath = await new Promise((resolve) =>
                    resolver.resolve(
                        {},
                        __dirname,
                        "./debug-require",
                        {},
                        (err?: Error | null, result?: string | false) =>
                            resolve(err ? false : result!),
                    ),
                );
            },
        );

        compiler.hooks.compilation.tap("DebugRequirePlugin", (compilation) => {
            compilation.mainTemplate.hooks.bootstrap.tap(
                "DebugRequirePlugin",
                (source: string, chunk: Chunk) => {
                    if (compilation.chunkGraph === undefined) {
                        return source;
                    }

                    const ids: [string, string | number][] = [];
                    let hasDebugRequire = false;
                    compilation.chunkGraph.hasModuleInGraph(
                        chunk,
                        (m) => {
                            if (m instanceof NormalModule) {
                                const id = compilation.chunkGraph.getModuleId(m);
                                if (m.resource === debugRequirePath) {
                                    hasDebugRequire = true;
                                }
                                for (const name of resolved.get(m.resource) ?? []) {
                                    ids.push([
                                        m.rawRequest.slice(0, m.rawRequest.lastIndexOf("!") + 1) +
                                            name,
                                        id,
                                    ]);
                                }
                            }
                            return false;
                        },
                        () => true,
                    );

                    if (!hasDebugRequire) {
                        return source;
                    }

                    ids.sort();
                    return Template.asString([
                        source,
                        `__webpack_require__.debugRequireIds = ${JSON.stringify(
                            Object.fromEntries(ids),
                            null,
                            "\t",
                        )};`,
                    ]);
                },
            );
        });
    }
}
