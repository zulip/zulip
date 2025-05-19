import fs from "node:fs";
import path from "node:path";

import type {Plugin} from "vite";

const INCLUDE_REGEX = /^ {0,3}-!([^!]+)!- *$/gm;

function resolveIncludes(text: string, currentDirectory: string): string {
    return text.replaceAll(INCLUDE_REGEX, (_match, includeFileName: string) => {
        let fullPath = path.resolve(currentDirectory, "include/" + includeFileName);
        if (currentDirectory.endsWith("include")) {
            // We are already inside the include directory, we don't
            // need to append `include` in this case.
            fullPath = path.resolve(currentDirectory, includeFileName);
        }

        if (!fs.existsSync(fullPath)) {
            throw new Error(`Included file not found: ${fullPath}`);
        }

        const includedContent = fs.readFileSync(fullPath, "utf8");
        return resolveIncludes(includedContent, path.dirname(fullPath));
    });
}

function removeDuplicateImports(code: string): string {
    // Included files will have import declarations inside them.
    // We need that since include files may as well use a component
    // not declared in the file including it.
    // But we may also have cases of imports being declared twice,
    // both the parent and child file are using the same component.
    // This function removes those duplicate imports.
    const lines = code.split("\n");
    const imports = new Set<string>();
    const resultLines: string[] = [];

    for (const line of lines) {
        if (line.startsWith("import ")) {
            if (imports.has(line)) {
                continue;
            }
            imports.add(line);
        }
        resultLines.push(line);
    }

    return resultLines.join("\n");
}

// When we import files in MDX, Astro already renders them and then
// places it in the appropriate slot. But our previous help center
// system heavily relied on the include files being macros. If we
// have an include that contains 2 list points and that include is
// followed and preceded by list points in the parent file, Astro
// will render three lists, one of the preceding points, then the
// points of the include files and the following points. There is
// no option to first include file, inject its contents and then
// render them all together in Astro (which would result in a single
// for our example). This plugin hopes to rectify that.
export default function preProcessMDXIncludePlugin(): Plugin {
    return {
        name: "pre-process-mdx-include",
        enforce: "pre",
        transform(text: string, filePath: string) {
            const currentDirectory = path.dirname(filePath);
            // We only render pages present directly in this directory,
            // and since our transformation function resolves includes
            // recursively, we don't need to worry about transferring
            // other files (i.e. the `include` directory).
            if (!currentDirectory.endsWith("src/content/docs")) {
                return text;
            }
            if (!filePath.endsWith(".mdx")) {
                return text;
            }

            text = resolveIncludes(text, currentDirectory);
            return removeDuplicateImports(text);
        },
    };
}
