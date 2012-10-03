/*jslint browser: true, devel: true, sloppy: true,
    plusplus: true, white: true, undef: true */
/*global $: false */

/* WARNING:

    This file is only included when Django's DEBUG = True and your
    host is in INTERNAL_IPS.

    Do not commit any code to zephyr.js which uses these functions.
    They are for debugging use only.

    The file may still be accessible under other circumstances, so do
    not put sensitive information here. */

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
