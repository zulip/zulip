"use strict";

const {strict: assert} = require("assert");

const {make_stub} = require("./lib/stub");
const {run_test} = require("./lib/test");

/*
    The previous example was a bit extreme.  Generally we just
    use the make_stub helper that comes with zjsunit.

    We will step away from the actual Zulip codebase for a
    second and just explore a contrived example.
*/

run_test("explore make_stub", ({override}) => {
    // Let's say you have to test the following code.

    const app = {
        /* istanbul ignore next */
        notify_server_of_deposit(deposit_amount) {
            // simulate difficulty
            throw new Error(`We cannot report this value without wifi: ${deposit_amount}`);
        },

        /* istanbul ignore next */
        pop_up_fancy_confirmation_screen(deposit_amount, label) {
            // simulate difficulty
            throw new Error(`We cannot make a ${label} dialog for amount ${deposit_amount}`);
        },
    };

    let balance = 40;

    function deposit_paycheck(paycheck_amount) {
        balance += paycheck_amount;
        app.notify_server_of_deposit(paycheck_amount);
        app.pop_up_fancy_confirmation_screen(paycheck_amount, "paycheck");
    }

    // Our deposit_paycheck should be easy to unit test for its
    // core functionality (updating your balance), but the side
    // effects get in the way.  We have to override them to do
    // the simple test here.

    override(app, "notify_server_of_deposit", () => {});
    override(app, "pop_up_fancy_confirmation_screen", () => {});
    deposit_paycheck(10);
    assert.equal(balance, 50);

    // But we can do a little better here.  Even though
    // the two side-effect functions are awkward here, we can
    // at least make sure they are invoked correctly.  Let's
    // use stubs.

    const notify_stub = make_stub();
    const pop_up_stub = make_stub();

    // This time we'll just use our override helper to connect the
    // stubs.
    override(app, "notify_server_of_deposit", notify_stub.f);
    override(app, "pop_up_fancy_confirmation_screen", pop_up_stub.f);

    deposit_paycheck(25);
    assert.equal(balance, 75);

    assert.deepEqual(notify_stub.get_args("amount"), {amount: 25});
    assert.deepEqual(pop_up_stub.get_args("amount", "label"), {amount: 25, label: "paycheck"});
});
