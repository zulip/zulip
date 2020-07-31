// This plugin exposes a version of require() to the browser console to assist
// debugging.  It also exposes the list of modules it knows about as the keys
// of the require.ids object.

import path from "path";

import webpack, {Template} from "webpack";

export default class DebugRequirePlugin {
    apply(compiler: webpack.Compiler): void {
        const resolved = new Map();
        const nameSymbol = Symbol("DebugRequirePluginName");
        let debugRequirePath: string | undefined;

        (compiler as any).resolverFactory.hooks.resolver
            .for("normal")
            .tap("DebugRequirePlugin", (resolver: any) => {
                resolver.getHook("beforeRawModule").tap("DebugRequirePlugin", (req: any) => {
                    req[nameSymbol] = req[nameSymbol] || req.request;
                });

                resolver.getHook("beforeRelative").tap("DebugRequirePlugin", (req: any) => {
                    const inPath = path.relative(compiler.context, req.path);
                    if (!inPath.startsWith("../")) {
                        req[nameSymbol] = req[nameSymbol] || "./" + inPath;
                    }
                });

                resolver.getHook("beforeResolved").tap("DebugRequirePlugin", (req: any) => {
                    if (req[nameSymbol]) {
                        const names = resolved.get(req.path);
                        if (names) {
                            names.add(req[nameSymbol]);
                        } else {
                            resolved.set(req.path, new Set([req[nameSymbol]]));
                        }
                    }
                });
            });

        compiler.hooks.beforeCompile.tapPromise(
            "DebugRequirePlugin",
            async ({normalModuleFactory}: any) => {
                const resolver = normalModuleFactory.getResolver("normal");
                debugRequirePath = await new Promise((resolve, reject) =>
                    resolver.resolve(
                        {},
                        __dirname,
                        "./debug-require",
                        {},
                        (err?: Error, result?: string) => (err ? reject(err) : resolve(result)),
                    ),
                );
            },
        );

        compiler.hooks.compilation.tap("DebugRequirePlugin", (compilation: any) => {
            compilation.mainTemplate.hooks.beforeStartup.tap(
                "DebugRequirePlugin",
                (source: string, chunk: webpack.compilation.Chunk) => {
                    const ids: [string, string | number][] = [];
                    let debugRequireId;
                    chunk.hasModuleInGraph(
                        ({resource, rawRequest, id}: any) => {
                            if (resource === debugRequirePath) {
                                debugRequireId = id;
                            }
                            for (const name of resolved.get(resource) || []) {
                                ids.push([
                                    rawRequest.slice(0, rawRequest.lastIndexOf("!") + 1) + name,
                                    id,
                                ]);
                            }
                            return false;
                        },
                        () => true,
                    );

                    if (debugRequireId === undefined) {
                        return source;
                    }

                    ids.sort();
                    const {requireFn} = compilation.mainTemplate;
                    return Template.asString([
                        source,
                        `${requireFn}(${JSON.stringify(
                            debugRequireId,
                        )}).initialize(${JSON.stringify(
                            Object.fromEntries(ids),
                            null,
                            "\t",
                        )}, modules);`,
                    ]);
                },
            );
        });
    }
}
