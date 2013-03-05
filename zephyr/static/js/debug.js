/* WARNING:

    This file is only included when Django's DEBUG = True and your
    host is in INTERNAL_IPS.

    Do not commit any code elsewhere which uses these functions.
    They are for debugging use only.

    The file may still be accessible under other circumstances, so do
    not put sensitive information here. */

// It's fine to use console.log etc. in this file.
/*jslint devel: true */

/*
      print_elapsed_time("foo", foo)

    evaluates to foo() and prints the elapsed time
    to the console along with the name "foo". */

function print_elapsed_time(name, fun) {
    var t0 = new Date().getTime();
    var out = fun();
    var t1 = new Date().getTime();
    console.log(name + ': ' + (t1 - t0) + ' ms');
    return out;
}

// Javascript stack trac functionality, adapted from:
// https://github.com/eriwen/javascript-stacktrace/blob/master/stacktrace.js
// The first function is just a helper.
function stringifyArguments(args) {
    var i, result = [];
    var slice = Array.prototype.slice;
    for (i = 0; i < args.length; ++i) {
        var arg = args[i];
        if (arg === undefined) {
            result[i] = 'undefined';
        } else if (arg === null) {
            result[i] = 'null';
        } else if (arg.constructor) {
            if (arg.constructor === Array) {
                if (arg.length < 3) {
                    result[i] = '[' + stringifyArguments(arg) + ']';
                } else {
                    result[i] = '[' + stringifyArguments(slice.call(arg, 0, 1)) + '...' + stringifyArguments(slice.call(arg, -1)) + ']';
                }
            } else if (arg.constructor === Object) {
                result[i] = '#object';
            } else if (arg.constructor === Function) {
                result[i] = '#function';
            } else if (arg.constructor === String) {
                result[i] = '"' + arg + '"';
            } else if (arg.constructor === Number) {
                result[i] = arg;
            }
        }
    }
    return result.join(',');
}

// Usage: console.log(verbose_stacktrace(arguments.callee));
function verbose_stacktrace(curr) {
    var ANON = '{anonymous}', fnRE = /function\s*([\w\-$]+)?\s*\(/i, stack = [], fn, args, maxStackSize = 50;
    while (curr && curr['arguments'] && stack.length < maxStackSize) {
        fn = curr.toString();
        args = Array.prototype.slice.call(curr['arguments'] || []);
        stack[stack.length] = fn + '(' + stringifyArguments(args) + ')';
        curr = curr.caller;
    }
    return stack;
}
