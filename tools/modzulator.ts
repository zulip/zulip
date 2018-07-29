#!/usr/bin/env ts-node-script

/*
  modzulator: Automatically convert CJS modules (with Zulip
  idiosyncrasies) to ES6 modules

  Copyright © 2018 Anders Kaseorg <andersk@mit.edu>

  Permission is hereby granted, free of charge, to any person
  obtaining a copy of this software and associated documentation files
  (the “Software”), to deal in the Software without restriction,
  including without limitation the rights to use, copy, modify, merge,
  publish, distribute, sublicense, and/or sell copies of the Software,
  and to permit persons to whom the Software is furnished to do so,
  subject to the following conditions:

  The above copyright notice and this permission notice shall be
  included in all copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND,
  EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
  MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
  NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
  BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
  ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
  CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
  SOFTWARE.
*/

/* eslint-disable consistent-return, no-plusplus, no-sync */

/// <reference types="node" />

import assert from "assert";
import child_process from "child_process";
import crypto from "crypto";
import fs from "fs";
import fsPath from "path";
import process from "process";

import {ASTNode, builders as b, namedTypes as n} from "ast-types";
import type * as K from "ast-types/gen/kinds";
import type {NodePath} from "ast-types/lib/node-path";
import type {Scope} from "ast-types/lib/scope";
import * as recast from "recast";
import * as babelParser from "recast/parsers/babel";
import * as tsParser from "recast/parsers/typescript";

function checkExpression(node: n.Node): node is K.ExpressionKind {
    return n.Expression.check(node);
}

function parseRequireCall(node: n.Node | null | undefined): string | null {
    if (
        n.CallExpression.check(node) &&
        n.Identifier.check(node.callee) &&
        node.callee.name === "require" &&
        node.arguments.length >= 1 &&
        n.StringLiteral.check(node.arguments[0])
    ) {
        return node.arguments[0].value;
    }
    return null;
}

function parseZrequireCall(node: n.Node | null | undefined): string | null {
    if (
        n.CallExpression.check(node) &&
        n.Identifier.check(node.callee) &&
        node.callee.name === "zrequire"
    ) {
        if (node.arguments.length === 1 && n.StringLiteral.check(node.arguments[0])) {
            return fsPath.join("static/js", node.arguments[0].value);
        } else if (node.arguments.length === 2 && n.StringLiteral.check(node.arguments[1])) {
            const fn = node.arguments[1].value;
            if (/^generated\/|^js\/|^shared\/|^third\//.test(fn)) {
                return fsPath.join("static", fn);
            }
        }
    }
    return null;
}

function parseSetGlobalCall(
    node: n.Node | null | undefined,
): {name: string; value: K.ExpressionKind} | null {
    if (
        n.CallExpression.check(node) &&
        n.Identifier.check(node.callee) &&
        node.callee.name === "set_global" &&
        node.arguments.length === 2 &&
        n.StringLiteral.check(node.arguments[0]) &&
        checkExpression(node.arguments[1])
    ) {
        return {name: node.arguments[0].value, value: node.arguments[1]};
    }
    return null;
}

function parseCjsRequireDeclarator(
    node: n.Node,
): {id: n.Identifier; member: n.Identifier | null; source: string} | null {
    if (n.VariableDeclarator.check(node)) {
        const id = node.id;
        let source;
        if (n.Identifier.check(id) && (source = parseRequireCall(node.init)) !== null) {
            return {
                id,
                member: null,
                source,
            };
        } else if (
            n.Identifier.check(id) &&
            n.MemberExpression.check(node.init) &&
            !node.init.computed &&
            n.Identifier.check(node.init.property) &&
            (source = parseRequireCall(node.init.object)) !== null
        ) {
            return {
                id,
                member: node.init.property,
                source,
            };
        } else if (
            n.ObjectPattern.check(id) &&
            id.properties.length === 1 &&
            n.ObjectProperty.check(id.properties[0]) &&
            n.Identifier.check(id.properties[0].key) &&
            n.Identifier.check(id.properties[0].value) &&
            (source = parseRequireCall(node.init)) !== null
        ) {
            return {
                id: id.properties[0].value,
                member: id.properties[0].key,
                source,
            };
        }
    }
    return null;
}

function parseCjsRequireStatement(
    node: n.Node,
): {id: n.Identifier; member: n.Identifier | null; source: string} | null {
    if (n.VariableDeclaration.check(node) && node.declarations.length === 1) {
        return parseCjsRequireDeclarator(node.declarations[0]);
    }
    return null;
}

function isCjsRequireStatement(node: n.Node): boolean {
    return (
        n.VariableDeclaration.check(node) &&
        node.declarations.length === 1 &&
        n.VariableDeclarator.check(node.declarations[0]) &&
        parseRequireCall(node.declarations[0].init) !== null
    );
}

type FreeVariables = {
    free: Set<string>;
    freeMut: Map<string, Set<string>>;
    requires: Set<string>;
    setGlobals: Set<string>;
    zrequires: Set<string>;
};

function getFreeVariables(ast: ASTNode): FreeVariables {
    const free = new Set<string>();
    const freeMut = new Map<string, Set<string>>();
    const requires = new Set<string>();
    const setGlobals = new Set<string>();
    const zrequires = new Set<string>();

    recast.visit(ast, {
        visitAssignmentExpression(path) {
            if (
                n.MemberExpression.check(path.node.left) &&
                n.Identifier.check(path.node.left.object) &&
                path.scope.lookup(path.node.left.object.name) === null
            ) {
                if (!freeMut.has(path.node.left.object.name)) {
                    freeMut.set(path.node.left.object.name, new Set<string>());
                }
                freeMut.get(path.node.left.object.name)!.add(recast.print(path.node.left).code);
            }
            this.traverse(path);
        },
        visitCallExpression(path) {
            const r = parseRequireCall(path.node);
            if (r !== null) {
                requires.add(r);
            }
            const zr = parseZrequireCall(path.node);
            if (zr !== null) {
                zrequires.add(zr);
            }
            const sg = parseSetGlobalCall(path.node);
            if (sg !== null) {
                setGlobals.add(sg.name);
            }
            this.traverse(path);
        },
        visitClassMethod(path): false | void {
            if (path.node.computed) {
                this.traverse(path);
            } else {
                this.visit(path.get("params"));
                this.visit(path.get("body"));
                return false;
            }
        },
        visitClassProperty(path): false | void {
            if (path.node.computed) {
                this.traverse(path);
            } else {
                this.visit(path.get("value"));
                return false;
            }
        },
        visitExpressionStatement(path): false | void {
            if (parseRequireCall(path.node.expression) !== null) {
                return false;
            }
            this.traverse(path);
        },
        visitIdentifier(path) {
            if (path.scope.lookup(path.node.name) === null) {
                free.add(path.node.name);
            }
            this.traverse(path);
        },
        visitImportDeclaration(path) {
            if (
                path.node.specifiers !== undefined &&
                path.node.specifiers.length !== 0 &&
                n.StringLiteral.check(path.node.source)
            ) {
                requires.add(path.node.source.value);
            }
            return false;
        },
        visitMemberExpression(path): false | void {
            if (path.node.computed) {
                this.traverse(path);
            } else {
                this.visit(path.get("object"));
                return false;
            }
        },
        visitObjectMethod(path): false | void {
            if (path.node.computed) {
                this.traverse(path);
            } else {
                this.visit(path.get("body"));
                return false;
            }
        },
        visitObjectProperty(path): false | void {
            if (path.node.computed) {
                this.traverse(path);
            } else {
                this.visit(path.get("value"));
                return false;
            }
        },
        visitProperty(path): false | void {
            if (path.node.computed) {
                this.traverse(path);
            } else {
                this.visit(path.get("value"));
                return false;
            }
        },
    });

    return {free, freeMut, requires, setGlobals, zrequires};
}

function parseObjectDeclaration(node: n.Node): string | null {
    if (
        n.VariableDeclaration.check(node) &&
        node.declarations.length === 1 &&
        n.VariableDeclarator.check(node.declarations[0]) &&
        n.Identifier.check(node.declarations[0].id) &&
        n.ObjectExpression.check(node.declarations[0].init) &&
        node.declarations[0].init.properties.length === 0
    ) {
        return node.declarations[0].id.name;
    }
    return null;
}

function parseExportsAssignmentStatement(node: n.Node): string | null {
    if (
        n.ExpressionStatement.check(node) &&
        n.AssignmentExpression.check(node.expression) &&
        node.expression.operator === "=" &&
        n.MemberExpression.check(node.expression.left) &&
        !node.expression.left.computed &&
        n.Identifier.check(node.expression.left.object) &&
        node.expression.left.object.name === "module" &&
        n.Identifier.check(node.expression.left.property) &&
        node.expression.left.property.name === "exports" &&
        n.Identifier.check(node.expression.right)
    ) {
        return node.expression.right.name;
    }
    return null;
}

function parseGlobalAssignmentStatement(
    node: n.Node,
): {outerName: string; globalName: string} | null {
    if (
        n.ExpressionStatement.check(node) &&
        n.AssignmentExpression.check(node.expression) &&
        node.expression.operator === "=" &&
        n.MemberExpression.check(node.expression.left) &&
        !node.expression.left.computed &&
        n.Identifier.check(node.expression.left.object) &&
        node.expression.left.object.name === "window" &&
        n.Identifier.check(node.expression.left.property) &&
        n.Identifier.check(node.expression.right)
    ) {
        return {
            outerName: node.expression.right.name,
            globalName: node.expression.left.property.name,
        };
    }
    return null;
}

type Cjs = {
    isObject: boolean;
    outerName: string;
    globalName: string | undefined;
};

function parseCjs(ast: ASTNode): Cjs | null {
    let ok = true;
    const isObject = new Map<string | null, boolean>();
    const globalName = new Map<string | null, string>();
    let outerName: string | null = null;

    recast.visit(ast, {
        visitClassDeclaration(path) {
            isObject.set(path.node.id!.name, false);
            return false;
        },
        visitExpressionStatement(path) {
            const ea = parseExportsAssignmentStatement(path.node);
            const ga = parseGlobalAssignmentStatement(path.node);
            if (ea !== null) {
                if (outerName !== null && outerName !== ea) {
                    ok = false;
                }
                outerName = ea;
            } else if (ga !== null) {
                globalName.set(ga.outerName, ga.globalName);
            }
            return false;
        },
        visitFunctionDeclaration(path) {
            isObject.set(path.node.id!.name, false);
            return false;
        },
        visitStatement() {
            return false;
        },
        visitVariableDeclaration(path) {
            const od = parseObjectDeclaration(path.node);
            if (od !== null) {
                isObject.set(od, true);
            } else if (
                path.node.declarations.length === 1 &&
                n.VariableDeclarator.check(path.node.declarations[0]) &&
                n.Identifier.check(path.node.declarations[0].id)
            ) {
                isObject.set(path.node.declarations[0].id.name, false);
            }
            return false;
        },
    });

    if (outerName === null) {
        outerName = "exports";
    }

    if (ok) {
        return {
            isObject: isObject.get(outerName) ?? true,
            outerName,
            globalName: globalName.get(outerName),
        };
    }
    return null;
}

function locString(file: string, node: n.Node): string {
    return `${file}:${node.loc?.start.line}:${node.loc?.start.column}`;
}

const free = new Map<string, FreeVariables>();
const freeMut = new Map<string, Set<string>>();

function cjsToEs6(
    file: string,
    {isObject, outerName, globalName}: Cjs,
    ast: ASTNode,
): ASTNode | null {
    let isExportsName = (path: NodePath, name: string): boolean =>
        (name === globalName || name === "exports") && path.scope.lookup(name) === null;
    const isExports = (path: NodePath): boolean =>
        (n.Identifier.check(path.node) && isExportsName(path, path.node.name)) ||
        (n.MemberExpression.check(path.node) &&
            !path.node.computed &&
            n.Identifier.check(path.node.object) &&
            path.node.object.name === "module" &&
            n.Identifier.check(path.node.property) &&
            path.node.property.name === "exports" &&
            path.scope.lookup(path.node.object.name) === null);
    const isExportsMember = (path: NodePath): string | null =>
        n.MemberExpression.check(path.node) &&
        !path.node.computed &&
        isExports(path.get("object")) &&
        n.Identifier.check(path.node.property)
            ? path.node.property.name
            : null;
    let ok = true;
    const exportable = new Map<string, Scope | null>();
    const exported = new Map<string, Scope | null>();
    let topLevel: n.Node | null = null;
    let unambiguous = false;
    recast.visit(ast, {
        visitClassDeclaration(path) {
            this.traverse(path);
            if (isExports(path.get("id"))) {
                if (isObject) {
                    console.log(
                        `${locString(file, path.node)}: skipping: declared ${
                            path.node.id!.name
                        } as a class`,
                    );
                    ok = false;
                }
                const comments = path.node.comments;
                path.get("comments").replace(null);
                path.replace(b.exportNamedDeclaration(path.node));
                path.get("comments").replace(comments);
                unambiguous = true;
            }
        },
        visitClassMethod(path): false | void {
            if (path.node.computed) {
                this.traverse(path);
            } else {
                this.visit(path.get("params"));
                this.visit(path.get("body"));
                return false;
            }
        },
        visitClassProperty(path): false | void {
            if (path.node.computed) {
                this.traverse(path);
            } else {
                this.visit(path.get("value"));
                return false;
            }
        },
        visitExpressionStatement(path): false | void {
            const ea = parseExportsAssignmentStatement(path.node);
            const ga = parseGlobalAssignmentStatement(path.node);
            let name: string | null;
            if ((ea !== null && ea === outerName) || (ga !== null && ga.outerName === outerName)) {
                path.replace();
                return false;
            } else if (
                isObject &&
                n.AssignmentExpression.check(path.node.expression) &&
                path.node.expression.operator === "=" &&
                (name = isExportsMember(path.get("expression", "left")))
            ) {
                if (path.parent.node === topLevel && !exported.has(name)) {
                    let decl;
                    let scope: Scope | null;
                    if (
                        n.Identifier.check(path.node.expression.right) &&
                        path.node.expression.right.name === name
                    ) {
                        // exports.foo = foo;  ↦  export { foo };
                        decl = b.exportNamedDeclaration(null, [
                            b.exportSpecifier.from({
                                exported: b.identifier(name),
                                local: b.identifier(name),
                            }),
                        ]);
                        scope = path.scope.lookup(name);
                    } else if (
                        n.Identifier.check(path.node.expression.right) &&
                        path.node.expression.right.name === "undefined"
                    ) {
                        // exports.foo = undefined;  ↦  export let foo;
                        decl = b.exportNamedDeclaration(
                            b.variableDeclaration("let", [
                                b.variableDeclarator(b.identifier(name), null),
                            ]),
                        );
                        scope = null;
                    } else if (
                        (n.FunctionExpression.check(path.node.expression.right) ||
                            n.ArrowFunctionExpression.check(path.node.expression.right)) &&
                        (path.node.expression.right.id === null ||
                            (n.Identifier.check(path.node.expression.right.id) &&
                                [name, `${outerName}_${name}`, `${outerName}__${name}`].includes(
                                    path.node.expression.right.id.name,
                                )))
                    ) {
                        // exports.foo = function (…) { … };  ↦  export function foo(…) { … }
                        decl = b.exportNamedDeclaration(
                            b.functionDeclaration.from({
                                id: b.identifier(name),
                                generator: path.node.expression.right.generator,
                                async: path.node.expression.right.async,
                                params: path.node.expression.right.params,
                                body: n.BlockStatement.check(path.node.expression.right.body)
                                    ? path.node.expression.right.body
                                    : b.blockStatement([
                                          b.returnStatement(path.node.expression.right.body),
                                      ]),
                            }),
                        );
                        scope = null;
                    } else {
                        // exports.foo = …;  ↦  export let foo = …;
                        decl = b.exportNamedDeclaration(
                            b.variableDeclaration("let", [
                                b.variableDeclarator(
                                    b.identifier(name),
                                    path.node.expression.right,
                                ),
                            ]),
                        );
                        scope = null;
                    }
                    decl.comments = path.node.comments;
                    path.replace(decl);
                    unambiguous = true;
                    if (
                        (path.scope.lookup(name) !== scope && path.scope.lookup(name) !== null) ||
                        (exportable.has(name) && exportable.get(name) !== scope)
                    ) {
                        console.log(
                            `${locString(file, path.node)}: skipping: export conflict with ${name}`,
                        );
                        ok = false;
                    }
                    exported.set(name, scope);
                    exportable.delete(name);
                    this.visit(path);
                    return false;
                } else if (
                    n.Identifier.check(path.node.expression.right) &&
                    path.node.expression.right.name === name
                ) {
                    // exports.foo = foo;
                    const scope = path.scope.lookup(name);
                    if (
                        (exported.has(name) && exported.get(name) !== scope) ||
                        (exportable.has(name) && exportable.get(name) !== scope)
                    ) {
                        console.log(
                            `${locString(file, path.node)}: skipping: export conflict with ${name}`,
                        );
                        ok = false;
                    }
                    if (!exported.has(name)) {
                        exportable.set(name, scope);
                    }
                    path.replace();
                    return false;
                }
                this.traverse(path);
            } else {
                this.traverse(path);
            }
        },
        visitFunctionDeclaration(path) {
            this.traverse(path);
            if (isExports(path.get("id"))) {
                if (isObject) {
                    console.log(
                        `${locString(file, path.node)}: skipping: declared ${
                            path.node.id!.name
                        } as a function`,
                    );
                    ok = false;
                }
                const comments = path.node.comments;
                path.get("comments").replace(null);
                path.replace(b.exportNamedDeclaration(path.node));
                path.get("comments").replace(comments);
                unambiguous = true;
            }
        },
        visitIdentifier(path) {
            if (isExports(path)) {
                if (isObject) {
                    console.log(
                        `${locString(file, path.node)}: skipping: unrecognized use of ${
                            path.node.name
                        }`,
                    );
                    ok = false;
                } else {
                    path.replace(b.identifier(outerName));
                }
            }
            this.traverse(path);
        },
        visitIfStatement(path): false | void {
            this.traverse(path);
        },
        visitMemberExpression(path): false | void {
            if (isExports(path)) {
                console.log(
                    `${locString(file, path.node)}: skipping: unrecognized use of ${
                        recast.print(path.node).code
                    }`,
                );
                ok = false;
            }
            let name: string | null;
            if (path.node.computed) {
                if (isObject && isExports(path.get("object"))) {
                    console.log(
                        `${locString(file, path.node)}: skipping: computed property of ${
                            recast.print(path.node.object).code
                        }`,
                    );
                    ok = false;
                }
                this.traverse(path);
            } else if (isObject && (name = isExportsMember(path))) {
                // exports.foo  ↦  foo
                const scope = path.scope.lookup(name);
                if (
                    (exported.has(name) && exported.get(name) !== scope) ||
                    (exportable.has(name) && exportable.get(name) !== scope)
                ) {
                    console.log(
                        `${locString(file, path.node)}: skipping: export conflict with ${name}`,
                    );
                    ok = false;
                }
                if (!exported.has(name)) {
                    exportable.set(name, scope);
                }
                path.replace(b.identifier(name));
                return false;
            } else {
                this.visit(path.get("object"));
                return false;
            }
        },
        visitProgram(path) {
            assert(topLevel === null);
            topLevel = path.node;
            const oldIsExportsName = isExportsName;
            const scope = path.scope.lookup(outerName);
            isExportsName = (path, name) =>
                (name === outerName && path.scope.lookup(name) === scope) ||
                oldIsExportsName(path, name);
            this.traverse(path);
            isExportsName = oldIsExportsName;
            topLevel = null;
            if (exported.has("delete") || exportable.has("delete")) {
                console.log(
                    `${locString(file, path.node)}: skipping: exports reserved keyword delete`,
                );
                ok = false;
            }
            let i = path.node.body.findIndex(
                (node) => !n.Directive.check(node) && !n.ImportDeclaration.check(node),
            );
            for (const [name, scope] of [...exportable].sort()) {
                if (scope !== null) {
                    console.log(
                        `${locString(file, path.node)}: skipping: export conflict with ${name}`,
                    );
                    ok = false;
                }
                // export let foo;
                path.get("body").insertAt(
                    i === -1 ? path.node.body.length : i++,
                    b.exportNamedDeclaration(
                        b.variableDeclaration("let", [
                            b.variableDeclarator(b.identifier(name), null),
                        ]),
                    ),
                );
                unambiguous = true;
            }
            if (!unambiguous) {
                path.get("body").push(b.exportNamedDeclaration(null));
            }
        },
        visitObjectMethod(path): false | void {
            if (path.node.computed) {
                this.traverse(path);
            } else {
                this.visit(path.get("body"));
                return false;
            }
        },
        visitObjectProperty(path): false | void {
            if (path.node.computed) {
                this.traverse(path);
            } else {
                this.visit(path.get("value"));
                return false;
            }
        },
        visitProperty(path): false | void {
            if (path.node.computed) {
                this.traverse(path);
            } else {
                this.visit(path.get("value"));
                return false;
            }
        },
        visitVariableDeclaration(path): false | void {
            const r = parseCjsRequireStatement(path.node);
            if (
                isObject &&
                parseObjectDeclaration(path.node) !== null &&
                isExports(path.get("declarations", 0, "id"))
            ) {
                path.replace();
                return false;
            } else if (
                !isObject &&
                path.node.declarations.length === 1 &&
                n.VariableDeclarator.check(path.node.declarations[0]) &&
                isExports(path.get("declarations", 0, "id"))
            ) {
                // let exports = …;  ↦  export let exports = …;
                this.traverse(path);
                const comments = path.node.comments;
                path.get("comments").replace(null);
                path.replace(b.exportNamedDeclaration(path.node));
                path.get("comments").replace(comments);
                unambiguous = true;
            } else if (r !== null) {
                // let foo = require("…");  ↦  import * as foo from "…";
                const comments = path.node.comments;
                path.get("comments").replace(null);
                path.replace(
                    b.importDeclaration(
                        [
                            r.member === null &&
                            (r.source.startsWith("./") || r.source.startsWith("../")) &&
                            (free.has(fsPath.join(fsPath.dirname(file), r.source) + ".ts") ||
                                free.has(fsPath.join(fsPath.dirname(file), r.source) + ".js"))
                                ? b.importNamespaceSpecifier(r.id)
                                : r.member === null || r.member.name === "default"
                                ? b.importDefaultSpecifier(r.id)
                                : b.importSpecifier(r.member, r.id),
                        ],
                        b.stringLiteral(r.source),
                    ),
                );
                path.get("comments").replace(comments);
                unambiguous = true;
                return false;
            } else {
                this.traverse(path);
            }
        },
    });
    return ok ? ast : null;
}

function isCjs(ast: ASTNode): boolean {
    let cjs = true;
    recast.visit(ast, {
        visitImportDeclaration() {
            cjs = false;
            return false;
        },
        visitExportNamedDeclaration() {
            cjs = false;
            return false;
        },
        visitStatement() {
            return false;
        },
    });
    return cjs;
}

function fixCjsRequire(m: Cjs, absSource: string, source: string, ast: ASTNode): ASTNode {
    const zrequireVariables = new Map<Scope | null, Set<string>>();

    recast.visit(ast, {
        visitCallExpression(path): false | void {
            if (
                !m.isObject &&
                (parseRequireCall(path.node) === source ||
                    parseZrequireCall(path.node) === absSource)
            ) {
                path.replace(b.memberExpression(path.node, b.identifier(m.outerName)));
                return false;
            }
            this.traverse(path);
        },
        visitExpressionStatement(path): false | void {
            if (parseZrequireCall(path.node.expression) === absSource) {
                path.replace();
                return false;
            }
            if (
                n.AssignmentExpression.check(path.node.expression) &&
                path.node.expression.operator === "=" &&
                n.MemberExpression.check(path.node.expression.left) &&
                n.Identifier.check(path.node.expression.left.object) &&
                zrequireVariables
                    .get(path.scope.lookup(path.node.expression.left.object.name))
                    ?.has(path.node.expression.left.object.name)
            ) {
                if (path.node.expression.left.computed) {
                    path.get("expression").replace(
                        b.callExpression(
                            b.memberExpression(
                                path.node.expression.left.object,
                                b.identifier("__Rewire__"),
                            ),
                            [path.node.expression.left.property, path.node.expression.right],
                        ),
                    );
                } else if (n.Identifier.check(path.node.expression.left.property)) {
                    path.get("expression").replace(
                        b.callExpression(
                            b.memberExpression(
                                path.node.expression.left.object,
                                b.identifier("__Rewire__"),
                            ),
                            [
                                b.stringLiteral(path.node.expression.left.property.name),
                                path.node.expression.right,
                            ],
                        ),
                    );
                }
            }
            this.traverse(path);
        },
        visitVariableDeclarator(path): false | void {
            if (
                !m.isObject &&
                (parseRequireCall(path.node.init) === source ||
                    parseZrequireCall(path.node.init) === absSource)
            ) {
                path.get("id").replace(
                    b.objectPattern([
                        b.property.from({
                            kind: "init",
                            key: b.identifier(m.outerName),
                            value: path.node.id,
                            shorthand:
                                n.Identifier.check(path.node.id) &&
                                m.outerName === path.node.id.name,
                        }),
                    ]),
                );
                this.traverse(path.get("id", "value"));
            } else if (
                m.isObject &&
                parseZrequireCall(path.node.init) === absSource &&
                n.Identifier.check(path.node.id)
            ) {
                const scope = path.scope.lookup(path.node.id.name);
                if (!zrequireVariables.has(scope)) {
                    zrequireVariables.set(scope, new Set<string>());
                }
                zrequireVariables.get(scope)!.add(path.node.id.name);
                return false;
            } else {
                this.traverse(path);
            }
        },
    });
    return ast;
}

function fixImport(m: Cjs, absSource: string, source: string, ast: ASTNode): ASTNode {
    if (!isCjs(ast)) {
        throw new Error("unimplemented");
    }
    return fixCjsRequire(m, absSource, source, ast);
}

function addCjsRequire(m: Cjs, source: string, ast: ASTNode): ASTNode {
    recast.visit(ast, {
        visitProgram(path) {
            const i = path.node.body.findIndex(
                (node) => !n.Directive.check(node) && !isCjsRequireStatement(node),
            );
            path.get("body").insertAt(
                i === -1 ? path.node.body.length : i,
                b.variableDeclaration("let", [
                    b.variableDeclarator(
                        m.isObject
                            ? b.identifier(m.globalName!)
                            : b.objectPattern([
                                  b.property.from({
                                      kind: "init",
                                      key: b.identifier(m.outerName),
                                      value: b.identifier(m.globalName!),
                                      shorthand: m.outerName === m.globalName!,
                                  }),
                              ]),
                        b.callExpression(b.identifier("require"), [b.stringLiteral(source)]),
                    ),
                ]),
            );
            return false;
        },
    });
    return ast;
}

function addEs6Import(m: Cjs, source: string, ast: ASTNode): ASTNode {
    recast.visit(ast, {
        visitExportNamedDeclaration(path) {
            if (path.node.declaration === null && path.node.specifiers!.length === 0) {
                path.replace();
            }
            return false;
        },
        visitStatement() {
            return false;
        },
        visitProgram(path) {
            const i = path.node.body.findIndex(
                (node) => !n.Directive.check(node) && !n.ImportDeclaration.check(node),
            );
            const specifier = m.isObject
                ? b.importNamespaceSpecifier(b.identifier(m.globalName!))
                : b.importSpecifier(b.identifier(m.outerName), b.identifier(m.globalName!));
            path.get("body").insertAt(
                i === -1 ? path.node.body.length : i,
                b.importDeclaration([specifier], b.stringLiteral(source)),
            );
            this.traverse(path);
        },
    });
    return ast;
}

function addImport(m: Cjs, source: string, ast: ASTNode): ASTNode {
    return isCjs(ast) ? addCjsRequire(m, source, ast) : addEs6Import(m, source, ast);
}

function fixSetGlobal(m: Cjs, source: string, ast: ASTNode): ASTNode {
    let needImport = true;
    let needEnable = true;
    let needSetGlobal = false;
    let needObject = false;

    function setMock(value: K.ExpressionKind): n.CallExpression {
        if (m.isObject && n.Identifier.check(value)) {
            needObject = true;
        }
        return b.callExpression(
            b.memberExpression(
                b.callExpression(b.identifier("rewiremock"), [b.stringLiteral(source)]),
                b.identifier("with"),
            ),
            [
                m.isObject
                    ? value
                    : b.objectExpression([
                          b.objectProperty.from({
                              key: b.identifier(m.outerName),
                              value,
                              shorthand: n.Identifier.check(value) && m.outerName === value.name,
                          }),
                      ]),
            ],
        );
    }

    recast.visit(ast, {
        visitCallExpression(path) {
            const sg = parseSetGlobalCall(path.node);
            if (sg !== null && sg.name === m.globalName) {
                path.replace(
                    b.memberExpression(
                        b.memberExpression(setMock(sg.value), b.identifier("mock")),
                        b.identifier("value"),
                    ),
                );
            } else if (sg !== null) {
                needSetGlobal = true;
            }
            if (
                n.MemberExpression.check(path.node.callee) &&
                !path.node.callee.computed &&
                n.Identifier.check(path.node.callee.object) &&
                path.node.callee.object.name === "rewiremock" &&
                n.Identifier.check(path.node.callee.property) &&
                path.node.callee.property.name === "enable"
            ) {
                needEnable = false;
            }
            this.traverse(path);
        },
        visitExpressionStatement(path) {
            const sg = parseSetGlobalCall(path.node.expression);
            if (sg !== null && sg.name === m.globalName) {
                path.get("expression").replace(setMock(sg.value));
            }
            this.traverse(path);
        },
        visitVariableDeclaration(path) {
            for (const [i, declaration] of [...path.node.declarations.entries()].reverse()) {
                if (n.VariableDeclarator.check(declaration)) {
                    const sg = parseSetGlobalCall(declaration.init);
                    if (
                        n.Identifier.check(declaration.id) &&
                        sg !== null &&
                        sg.name === m.globalName
                    ) {
                        path.get("declarations", i, "init").replace(sg.value);
                        path.insertAfter(b.expressionStatement(setMock(declaration.id)));
                    }
                    if (
                        n.Identifier.check(declaration.id) &&
                        declaration.id.name === "rewiremock" &&
                        parseRequireCall(declaration.init) === "rewiremock/node"
                    ) {
                        needImport = false;
                    }
                }
            }
            this.traverse(path);
        },
    });

    if (needObject) {
        const objectInits = new Map<Scope, Set<string>>();
        recast.visit(ast, {
            visitBlockStatement(path): false {
                for (const i of [...path.node.body.keys()].reverse()) {
                    this.traverse(path.get("body", i));
                }
                return false;
            },
            visitCallExpression(path) {
                if (
                    n.MemberExpression.check(path.node.callee) &&
                    !path.node.callee.computed &&
                    n.CallExpression.check(path.node.callee.object) &&
                    n.Identifier.check(path.node.callee.object.callee) &&
                    path.node.callee.object.callee.name === "rewiremock" &&
                    path.node.callee.object.arguments.length === 1 &&
                    n.StringLiteral.check(path.node.callee.object.arguments[0]) &&
                    path.node.callee.object.arguments[0].value === source &&
                    n.Identifier.check(path.node.callee.property) &&
                    path.node.callee.property.name === "with" &&
                    path.node.arguments.length === 1 &&
                    n.Identifier.check(path.node.arguments[0])
                ) {
                    const scope = path.scope.lookup(path.node.arguments[0].name);
                    if (!objectInits.has(scope)) {
                        objectInits.set(scope, new Set<string>());
                    }
                    objectInits.get(scope)!.add(path.node.arguments[0].name);
                }
                this.traverse(path);
            },
            visitProgram(path): false {
                for (const i of [...path.node.body.keys()].reverse()) {
                    this.traverse(path.get("body", i));
                }
                return false;
            },
            visitVariableDeclarator(path) {
                if (
                    n.Identifier.check(path.node.id) &&
                    n.ObjectExpression.check(path.node.init) &&
                    objectInits.get(path.scope.lookup(path.node.id.name))?.has(path.node.id.name)
                ) {
                    path.get("init", "properties").insertAt(
                        0,
                        b.objectProperty(b.identifier("__esModule"), b.booleanLiteral(true)),
                    );
                }
                this.traverse(path);
            },
        });
    }

    if (needImport) {
        ast = addImport(
            {isObject: true, outerName: "rewiremock", globalName: "rewiremock"},
            "rewiremock/node",
            ast,
        );
    }

    if (needEnable) {
        let foundZrequire = false;
        recast.visit(ast, {
            visitCallExpression(path) {
                if (
                    n.Identifier.check(path.node.callee) &&
                    ["reset_module", "zrequire"].includes(path.node.callee.name)
                ) {
                    foundZrequire = true;
                }
                this.traverse(path);
            },

            visitProgram(path) {
                let first: number | undefined;
                for (let i = 0; i < path.node.body.length; i++) {
                    this.traverse(path.get("body", i));
                    if (foundZrequire) {
                        first = i;
                        break;
                    }
                }
                if (first !== undefined) {
                    path.get("body").insertAt(
                        first,
                        b.expressionStatement(
                            b.callExpression(
                                b.memberExpression(
                                    b.identifier("rewiremock"),
                                    b.identifier("enable"),
                                ),
                                [],
                            ),
                        ),
                    );
                }
                path.get("body").insertAt(
                    path.node.body.length,
                    b.expressionStatement(
                        b.callExpression(
                            b.memberExpression(b.identifier("rewiremock"), b.identifier("disable")),
                            [],
                        ),
                    ),
                );
                return false;
            },
        });
    }
    if (!needSetGlobal) {
        recast.visit(ast, {
            visitVariableDeclarator(path): false | void {
                if (
                    parseRequireCall(path.node.init) === "../zjsunit/namespace" &&
                    n.ObjectPattern.check(path.node.id)
                ) {
                    for (const [i, property] of [...path.node.id.properties.entries()].reverse()) {
                        if (
                            n.ObjectProperty.check(property) &&
                            n.Identifier.check(property.key) &&
                            property.key.name === "set_global"
                        ) {
                            path.get("id", "properties", i).replace();
                        }
                    }
                    if (path.node.id.properties.length === 0) {
                        path.prune();
                        return false;
                    }
                }
                this.traverse(path);
            },
        });
    }
    return ast;
}

function parse(file: string): ASTNode {
    return recast.parse(fs.readFileSync(file, "utf-8"), {
        parser: fsPath.extname(file) === ".ts" ? tsParser : babelParser,
    });
}

function hashFiles(files: Iterable<string>): Buffer {
    const hash = crypto.createHash("sha256");
    for (const file of files) {
        const contents = fs.readFileSync(file);
        hash.update(contents.length + "\n");
        hash.update(contents);
    }
    return hash.digest();
}

const args = process.argv.slice(2);

let runNodeTests = false;

while (true) {
    if (args[0] === "--node-tests") {
        runNodeTests = true;
        args.shift();
    } else {
        break;
    }
}

let p = child_process.spawnSync(
    "git",
    ["ls-files", "-z", "static/js/**.js", "static/shared/js/**.js"],
    {encoding: "utf8"},
);
if (p.status !== 0) {
    throw new Error("git ls-files failed");
}
const allJsFiles = p.stdout.split("\0");
if (allJsFiles.pop() !== "") {
    throw new Error("expected trailing NUL");
}

p = child_process.spawnSync("git", ["ls-files", "-z", "frontend_tests/node_tests/*.js"], {
    encoding: "utf8",
});
if (p.status !== 0) {
    throw new Error("git ls-files failed");
}
const allNodeTests = p.stdout.split("\0");
if (allNodeTests.pop() !== "") {
    throw new Error("expected trailing NUL");
}

for (const file of [...allJsFiles, ...allNodeTests]) {
    console.log(`${file}: parsing`);
    const ast = parse(file);
    const freeVariables = getFreeVariables(ast);
    free.set(file, freeVariables);
    for (const [v, cs] of freeVariables.freeMut) {
        freeMut.set(
            v,
            new Set<string>([...(freeMut.get(v) ?? []), ...cs]),
        );
    }
}

for (const file of args) {
    const ast = parse(file);
    if (!isCjs(ast)) {
        console.log(`${file}: skipping: not CJS`);
        continue;
    }
    const m = parseCjs(ast);
    if (m === null) {
        console.log(`${file}: skipping: could not interpret CJS module`);
        continue;
    }
    if (m.globalName !== undefined && freeMut.has(m.globalName)) {
        for (const c of freeMut.get(m.globalName)!) {
            console.log(`${file}: skipping: has a mutable member ${c}`);
        }
        continue;
    }
    const ast1 = cjsToEs6(file, m, ast);
    if (ast1 === null) {
        continue;
    }
    console.log(`${file}: writing`);
    fs.writeFileSync(file, recast.print(ast1).code);
    const modifiedJs = new Set([file]);
    const modifiedOther: string[] = [];

    const {base: _base, ...parts} = fsPath.parse(file);
    const absolute = fsPath.format({...parts, ext: ""});
    for (const file1 of [...allJsFiles, ...allNodeTests]) {
        if (file1 === file) {
            continue;
        }
        const {base: _base, ...parts} = fsPath.parse(fsPath.relative(fsPath.dirname(file1), file));
        let relative = fsPath.format({...parts, ext: ""});
        if (!relative.startsWith("../")) {
            relative = "./" + relative;
        }
        const freeVariables = free.get(file1)!;
        if (
            (!m.isObject && freeVariables.requires.has(relative)) ||
            freeVariables.zrequires.has(absolute)
        ) {
            console.log(`${file1}: fixing import for ${relative}`);
            fs.writeFileSync(
                file1,
                recast.print(fixImport(m, absolute, relative, parse(file1))).code,
            );
            modifiedJs.add(file1);
        }
        if (m.globalName !== undefined && freeVariables.free.has(m.globalName)) {
            console.log(`${file1}: adding import for ${relative}`);
            fs.writeFileSync(file1, recast.print(addImport(m, relative, parse(file1))).code);
            modifiedJs.add(file1);
        }
        if (m.globalName !== undefined && freeVariables.setGlobals.has(m.globalName)) {
            console.log(`${file1}: fixing set_global for ${m.globalName}`);
            fs.writeFileSync(file1, recast.print(fixSetGlobal(m, relative, parse(file1))).code);
            modifiedJs.add(file1);
        }
    }

    if (m.globalName !== undefined) {
        console.log(`.eslintrc.json: removing exemption for ${m.globalName}`);
        fs.writeFileSync(
            ".eslintrc.json",
            fs
                .readFileSync(".eslintrc.json", "utf8")
                .replace(`,\n                "${m.globalName}": false`, ""),
        );
        modifiedOther.push(".eslintrc.json");
        console.log(`global.d.ts: removing declaration for ${m.globalName}`);
        fs.writeFileSync(
            "static/js/global.d.ts",
            fs
                .readFileSync("static/js/global.d.ts", "utf8")
                .replace(`declare let ${m.globalName}: any;\n`, ""),
        );
        modifiedOther.push("static/js/global.d.ts");
    }

    if (runNodeTests) {
        console.log("running Node tests");
        if (
            child_process.spawnSync(
                "node",
                [
                    "frontend_tests/zjsunit/index.js",
                    ...allNodeTests.map((filename) => fsPath.join("../..", filename)),
                ],
                {env: {...process.env, TZ: "UTC"}, stdio: "inherit"},
            ).status !== 0
        ) {
            console.log("test-js-with-node failed, reverting");
            if (
                child_process.spawnSync(
                    "git",
                    ["checkout", "--", ...modifiedJs, ...modifiedOther],
                    {stdio: "inherit"},
                ).status !== 0
            ) {
                throw new Error("git checkout failed");
            }
            continue;
        }
    }

    console.log("running eslint --fix");
    let tries = 5;
    let hash = hashFiles(modifiedJs);
    while (true) {
        const oldHash = hash;
        if (
            child_process.spawnSync("node_modules/.bin/eslint", ["--fix", "--", ...modifiedJs], {
                stdio: "inherit",
            }).status === 0
        ) {
            break;
        }
        tries -= 1;
        if (tries === 0 || (hash = hashFiles(modifiedJs)).equals(oldHash)) {
            throw new Error("eslint --fix failed");
        }
        console.log("rerunning eslint --fix");
    }

    console.log("running prettier --write");
    if (
        child_process.spawnSync("node_modules/.bin/prettier", ["--write", "--", ...modifiedJs], {
            stdio: "inherit",
        }).status !== 0
    ) {
        throw new Error("prettier --write failed");
    }

    console.log("committing");
    if (
        child_process.spawnSync(
            "git",
            [
                "commit",
                "-s",
                "-m",
                `js: Convert ${file} to ES6 module.`,
                "--",
                ...modifiedJs,
                ...modifiedOther,
            ],
            {stdio: "inherit"},
        ).status !== 0
    ) {
        throw new Error("git commit failed");
    }
}

console.log("All done!");
