#! /usr/bin/env node

"use strict";

const fs = require("fs");

const parser = require("@babel/parser").parse;
const traverse = require("@babel/traverse").default;

const strings = [];

const paths = process.argv.slice(2);

const extract_strings = {
    CallExpression(path) {
        const callee = path.node.callee;
        const is_i18n_call =
            callee.type === "MemberExpression" &&
            callee.object &&
            callee.object.name === "i18n" &&
            callee.property &&
            callee.property.name === "t";
        if (!is_i18n_call) {
            return;
        }
        const args = path.node.arguments;
        if (args.length > 0 && args[0].type === "StringLiteral") {
            const string = {
                string: args[0].value,
            };
            if (args[1] && args[1].type === "ObjectExpression") {
                args[1].properties.forEach((p) => {
                    if (
                        p.key.type === "Identifier" &&
                        p.key.name === "context" &&
                        p.value.type === "StringLiteral"
                    ) {
                        string.context = p.value.value;
                    }
                });
            }
            strings.push(string);
        }
    },
};

paths.forEach((path) => {
    // eslint-disable-next-line no-sync
    if (fs.lstatSync(path).isDirectory()) {
        return;
    }
    const file = fs.readFileSync(path).toString(); // eslint-disable-line no-sync
    const ast = parser(file, {
        plugins: ["classProperties", "typescript"],
        sourceType: "unambiguous",
    });
    traverse(ast, extract_strings);
});

console.log(JSON.stringify(strings));
