import {FlatCompat} from "@eslint/eslintrc";
import js from "@eslint/js";
import confusingBrowserGlobals from "confusing-browser-globals";
import prettier from "eslint-config-prettier";
import formatjs from "eslint-plugin-formatjs";
import importPlugin from "eslint-plugin-import";
import noJquery from "eslint-plugin-no-jquery";
import unicorn from "eslint-plugin-unicorn";
import globals from "globals";
import tseslint from "typescript-eslint";

const compat = new FlatCompat({baseDirectory: import.meta.dirname});

export default [
    {
        files: ["tools/check-openapi"],
    },
    {
        // This is intended for generated files and vendored third-party files.
        // For our source code, instead of adding files here, consider using
        // specific eslint-disable comments in the files themselves.
        ignores: [
            "docs/_build",
            "static/generated",
            "static/webpack-bundles",
            "var",
            "web/generated",
            "web/third",
            "zulip-current-venv",
            "zulip-py3-venv",
        ],
    },
    js.configs.recommended,
    importPlugin.flatConfigs.recommended,
    ...compat.extends("plugin:no-jquery/recommended", "plugin:no-jquery/deprecated"),
    unicorn.configs["flat/recommended"],
    prettier,
    {
        plugins: {
            formatjs,
            "no-jquery": noJquery,
        },
        linterOptions: {
            reportUnusedDisableDirectives: true,
        },
        languageOptions: {
            ecmaVersion: "latest",
            parserOptions: {
                warnOnUnsupportedTypeScriptVersion: false,
            },
        },
        settings: {
            formatjs: {
                additionalFunctionNames: ["$t", "$t_html"],
            },
            "no-jquery": {
                collectionReturningPlugins: {expectOne: "always"},
                variablePattern: "^\\$(?!t$|t_html$).",
            },
        },
        rules: {
            "array-callback-return": "error",
            "arrow-body-style": "error",
            "consistent-return": "error",
            curly: "error",
            "dot-notation": "error",
            eqeqeq: "error",
            "formatjs/enforce-default-message": ["error", "literal"],
            "formatjs/enforce-placeholders": [
                "error",
                {ignoreList: ["b", "code", "em", "i", "kbd", "p", "strong"]},
            ],
            "formatjs/no-id": "error",
            "guard-for-in": "error",
            "import/extensions": ["error", "ignorePackages"],
            "import/first": "error",
            "import/newline-after-import": "error",
            "import/no-cycle": ["error", {ignoreExternal: true}],
            "import/no-duplicates": "error",
            "import/no-self-import": "error",
            "import/no-unresolved": "off",
            "import/no-useless-path-segments": "error",
            "import/order": ["error", {alphabetize: {order: "asc"}, "newlines-between": "always"}],
            "import/unambiguous": "error",
            "lines-around-directive": "error",
            "new-cap": "error",
            "no-alert": "error",
            "no-array-constructor": "error",
            "no-bitwise": "error",
            "no-caller": "error",
            "no-constant-condition": ["error", {checkLoops: false}],
            "no-div-regex": "error",
            "no-else-return": "error",
            "no-eval": "error",
            "no-implicit-coercion": "error",
            "no-implied-eval": "error",
            "no-jquery/no-append-html": "error",
            "no-jquery/no-constructor-attributes": "error",
            "no-jquery/no-parse-html-literal": "error",
            "no-label-var": "error",
            "no-labels": "error",
            "no-loop-func": "error",
            "no-multi-str": "error",
            "no-new-func": "error",
            "no-new-wrappers": "error",
            "no-object-constructor": "error",
            "no-octal-escape": "error",
            "no-plusplus": "error",
            "no-proto": "error",
            "no-restricted-globals": ["error", ...confusingBrowserGlobals],
            "no-return-assign": "error",
            "no-script-url": "error",
            "no-self-compare": "error",
            "no-throw-literal": "error",
            "no-undef-init": "error",
            "no-unneeded-ternary": ["error", {defaultAssignment: false}],
            "no-unused-expressions": "error",
            "no-unused-vars": [
                "error",
                {args: "all", argsIgnorePattern: "^_", ignoreRestSiblings: true},
            ],
            "no-use-before-define": ["error", {functions: false, variables: false}],
            "no-useless-concat": "error",
            "no-useless-constructor": "error",
            "no-var": "error",
            "object-shorthand": ["error", "always", {avoidExplicitReturnArrows: true}],
            "one-var": ["error", "never"],
            "prefer-arrow-callback": "error",
            "prefer-const": ["error", {ignoreReadBeforeAssign: true}],
            radix: "error",
            "sort-imports": ["error", {ignoreDeclarationSort: true}],
            "spaced-comment": ["error", "always", {markers: ["/"]}],
            strict: "error",
            "unicorn/consistent-function-scoping": "off",
            "unicorn/filename-case": "off",
            "unicorn/no-await-expression-member": "off",
            "unicorn/no-negated-condition": "off",
            "unicorn/no-null": "off",
            "unicorn/no-process-exit": "off",
            "unicorn/no-useless-undefined": "off",
            "unicorn/numeric-separators-style": "off",
            "unicorn/prefer-global-this": "off",
            "unicorn/prefer-string-raw": "off",
            "unicorn/prefer-ternary": "off",
            "unicorn/prefer-top-level-await": "off",
            "unicorn/prevent-abbreviations": "off",
            "unicorn/switch-case-braces": "off",
            "valid-typeof": ["error", {requireStringLiterals: true}],
            yoda: "error",
        },
    },
    {
        files: ["**/*.cjs"],
        languageOptions: {
            sourceType: "commonjs",
        },
    },
    {
        files: ["web/tests/**"],
        rules: {
            "no-jquery/no-selector-prop": "off",
        },
    },
    {
        files: ["web/e2e-tests/**"],
        languageOptions: {
            globals: {
                zulip_test: "readonly",
            },
        },
    },
    ...[
        ...tseslint.configs.strictTypeChecked,
        ...tseslint.configs.stylisticTypeChecked,
        importPlugin.flatConfigs.typescript,
    ].map((config) => ({
        ...config,
        files: ["**/*.cts", "**/*.mts", "**/*.ts"],
    })),
    {
        files: ["**/*.cts", "**/*.mts", "**/*.ts"],
        languageOptions: {
            globals: {
                JQuery: "readonly",
            },
            parserOptions: {
                projectService: true,
                tsConfigRootDir: import.meta.dirname,
            },
        },
        settings: {
            "import/resolver": {
                node: {
                    extensions: [".ts", ".d.ts", ".js"],
                },
            },
        },
        rules: {
            "no-use-before-define": "off",
            "@typescript-eslint/consistent-type-assertions": ["error", {assertionStyle: "never"}],
            "@typescript-eslint/consistent-type-definitions": ["error", "type"],
            "@typescript-eslint/consistent-type-imports": "error",
            "@typescript-eslint/explicit-function-return-type": ["error", {allowExpressions: true}],
            "@typescript-eslint/member-ordering": "error",
            "@typescript-eslint/method-signature-style": "error",
            "@typescript-eslint/no-non-null-assertion": "off",
            "@typescript-eslint/no-unnecessary-condition": "off",
            "@typescript-eslint/no-unnecessary-qualifier": "error",
            "@typescript-eslint/no-unused-vars": [
                "error",
                {args: "all", argsIgnorePattern: "^_", ignoreRestSiblings: true},
            ],
            "@typescript-eslint/no-use-before-define": [
                "error",
                {functions: false, variables: false},
            ],
            "@typescript-eslint/parameter-properties": "error",
            "@typescript-eslint/promise-function-async": "error",
            "@typescript-eslint/restrict-plus-operands": ["error", {}],
            "@typescript-eslint/restrict-template-expressions": ["error", {}],
            "no-undef": "error",
        },
    },
    {
        files: ["**/*.d.ts"],
        rules: {
            "import/unambiguous": "off",
        },
    },
    {
        files: ["**"],
        ignores: ["web/shared/**", "web/src/**"],
        languageOptions: {
            globals: globals.node,
        },
    },
    {
        files: ["web/e2e-tests/**", "web/tests/**"],
        languageOptions: {
            globals: {
                CSS: "readonly",
                document: "readonly",
                navigator: "readonly",
                window: "readonly",
            },
        },
        rules: {
            "formatjs/no-id": "off",
            "new-cap": "off",
        },
    },
    {
        files: ["web/debug-require.cjs"],
        rules: {
            "no-var": "off",
            "object-shorthand": "off",
            "prefer-arrow-callback": "off",
        },
    },
    {
        files: ["web/shared/**", "web/src/**"],
        settings: {
            "import/resolver": {
                webpack: {
                    config: {},
                },
            },
        },
        rules: {
            "no-console": "error",
        },
    },
    {
        files: ["web/src/**"],
        languageOptions: {
            globals: {
                ...globals.browser,
                DEVELOPMENT: "readonly",
                StripeCheckout: "readonly",
                ZULIP_VERSION: "readonly",
            },
        },
    },
    {
        files: ["web/shared/**"],
        languageOptions: {
            globals: globals["shared-node-browser"],
        },
        rules: {
            "import/no-restricted-paths": [
                "error",
                {
                    zones: [
                        {
                            target: "./web/shared",
                            from: ".",
                            except: ["./node_modules", "./web/shared"],
                        },
                    ],
                },
            ],
            "unicorn/prefer-string-replace-all": "off",
        },
    },
];
