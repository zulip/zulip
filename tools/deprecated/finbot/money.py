#!/usr/bin/env python2.7
from __future__ import print_function
import datetime
import monthdelta

def parse_date(date_str):
    return datetime.datetime.strptime(date_str, "%Y-%m-%d")

def unparse_date(date_obj):
    return date_obj.strftime("%Y-%m-%d")

class Company(object):
    def __init__(self, name):
        self.name = name
        self.flows = []
        self.verbose = False

    def __str__(self):
        return self.name

    def add_flow(self, flow):
        self.flows.append(flow)

    def cash_at_date_internal(self, start_date, end_date):
        cash = 0
        for flow in self.flows:
            delta = flow.cashflow(start_date, end_date, (end_date - start_date).days)
            cash += delta
            if self.verbose:
                print(flow.name, round(delta, 2))
        return round(cash, 2)

    def cash_at_date(self, start, end):
        start_date = parse_date(start)
        end_date = parse_date(end)
        return self.cash_at_date_internal(start_date, end_date)

    def cash_monthly_summary(self, start, end):
        start_date = parse_date(start)
        cur_date = parse_date(start)
        end_date = parse_date(end)
        while cur_date <= end_date:
            print(cur_date, self.cash_at_date_internal(start_date, cur_date))
            cur_date += monthdelta.MonthDelta(1)
            if self.verbose:
                print()

# CashFlow objects fundamentally just provide a function that says how
# much cash has been spent by that source at each time
#
# The API is that one needs to define a function .cashflow(date)
class CashFlow(object):
    def __init__(self, name):
        self.name = name

class FixedCost(CashFlow):
    def __init__(self, name, amount):
        super(FixedCost, self).__init__(name)
        self.cost = -amount

    def cashflow(self, start, end, days):
        return self.cost

class ConstantCost(CashFlow):
    def __init__(self, name, amount):
        super(ConstantCost, self).__init__(name)
        self.rate = -amount

    def cashflow(self, start, end, days):
        return self.rate * days / 365.

class PeriodicCost(CashFlow):
    def __init__(self, name, amount, start, interval):
        super(PeriodicCost, self).__init__(name)
        self.amount = -amount
        self.start = parse_date(start)
        self.interval = interval

    def cashflow(self, start, end, days):
        cur = self.start
        delta = 0
        while (cur <= end):
            if cur >= start:
                delta += self.amount
            cur += datetime.timedelta(days=self.interval)
        return delta

class MonthlyCost(CashFlow):
    def __init__(self, name, amount, start):
        super(MonthlyCost, self).__init__(name)
        self.amount = -amount
        self.start = parse_date(start)

    def cashflow(self, start, end, days):
        cur = self.start
        delta = 0
        while (cur <= end):
            if cur >= start:
                delta += self.amount
            cur += monthdelta.MonthDelta(1)
        return delta

class TotalCost(CashFlow):
    def __init__(self, name, *args):
        self.name = name
        self.flows = args

    def cashflow(self, start, end, days):
        return sum(cost.cashflow(start, end, days) for cost in self.flows)

class SemiMonthlyCost(TotalCost):
    def __init__(self, name, amount, start1, start2 = None):
        if start2 is None:
            start2 = unparse_date(parse_date(start1) + datetime.timedelta(days=14))
        super(SemiMonthlyCost, self).__init__(name,
                                              MonthlyCost(name, amount, start1),
                                              MonthlyCost(name, amount, start2)
                                              )

class SemiMonthlyWagesNoTax(SemiMonthlyCost):
    def __init__(self, name, wage, start):
        super(SemiMonthlyWagesNoTax, self).__init__(name, self.compute_wage(wage), start)

    def compute_wage(self, wage):
        return wage / 24.

class SemiMonthlyWages(SemiMonthlyWagesNoTax):
    def compute_wage(self, wage):
        fica_tax = min(wage, 110100) * 0.062 + wage * 0.0145
        unemp_tax = 450
        return (wage + fica_tax + unemp_tax) / 24.

    def __init__(self, name, wage, start):
        super(SemiMonthlyWages, self).__init__(name, wage, start)

class DelayedCost(CashFlow):
    def __init__(self, start, base_model):
        super(DelayedCost, self).__init__("Delayed")
        self.base_model = base_model
        self.start = parse_date(start)

    def cashflow(self, start, end, days):
        start = max(start, self.start)
        if start > end:
            return 0
        time_delta = (end-start).days
        return self.base_model.cashflow(start, end, time_delta)

class BiweeklyWagesNoTax(PeriodicCost):
    def __init__(self, name, wage, start):
        super(BiweeklyWagesNoTax, self).__init__(name, self.compute_wage(wage), start, 14)

    def compute_wage(self, wage):
        # You would think this calculation would be (wage * 14 /
        # 365.24), but you'd be wrong -- companies paying biweekly
        # wages overpay by about 0.34% by doing the math this way
        return wage / 26.

class BiweeklyWages(BiweeklyWagesNoTax):
    def compute_wage(self, wage):
        fica_tax = min(wage, 110100) * 0.062 + wage * 0.0145
        unemp_tax = 450
        # You would think this calculation would be (wage * 14 /
        # 365.24), but you'd be wrong -- companies paying biweekly
        # wages overpay by about 0.34% by doing the math this way
        return (wage + fica_tax + unemp_tax) / 26.

    def __init__(self, name, wage, start):
        super(BiweeklyWages, self).__init__(name, wage, start)



if __name__ == "__main__":
    # Tests
    c = Company("Example Inc")
    c.add_flow(FixedCost("Initial Cash", -500000))
    c.add_flow(FixedCost("Incorporation", 500))
    assert(c.cash_at_date("2012-01-01", "2012-03-01") == 500000 - 500)
    c.add_flow(FixedCost("Incorporation", -500))

    c.add_flow(ConstantCost("Office", 50000))
    assert(c.cash_at_date("2012-01-01", "2012-01-02") == 500000 - round(50000*1/365., 2))
    c.add_flow(ConstantCost("Office", -50000))

    c.add_flow(PeriodicCost("Payroll", 4000, "2012-01-05", 14))
    assert(c.cash_at_date("2012-01-01", "2012-01-02") == 500000)
    assert(c.cash_at_date("2012-01-01", "2012-01-06") == 500000 - 4000)
    c.add_flow(PeriodicCost("Payroll", -4000, "2012-01-05", 14))

    c.add_flow(DelayedCost("2012-02-01", ConstantCost("Office", 50000)))
    assert(c.cash_at_date("2012-01-01", "2012-01-05") == 500000)
    assert(c.cash_at_date("2012-01-01", "2012-02-05") == 500000 - round(50000*4/365., 2))
    c.add_flow(DelayedCost("2012-02-01", ConstantCost("Office", -50000)))

    c.add_flow(DelayedCost("2012-02-01", FixedCost("Financing", 50000)))
    assert(c.cash_at_date("2012-01-01", "2012-01-15") == 500000)
    c.add_flow(DelayedCost("2012-02-01", FixedCost("Financing", -50000)))

    c.add_flow(SemiMonthlyCost("Payroll", 4000, "2012-01-01"))
    assert(c.cash_at_date("2012-01-01", "2012-01-01") == 500000 - 4000)
    assert(c.cash_at_date("2012-01-01", "2012-01-14") == 500000 - 4000)
    assert(c.cash_at_date("2012-01-01", "2012-01-15") == 500000 - 4000 * 2)
    assert(c.cash_at_date("2012-01-01", "2012-01-31") == 500000 - 4000 * 2)
    assert(c.cash_at_date("2012-01-01", "2012-02-01") == 500000 - 4000 * 3)
    assert(c.cash_at_date("2012-01-01", "2012-02-15") == 500000 - 4000 * 4)
    c.add_flow(SemiMonthlyCost("Payroll", -4000, "2012-01-01"))

    c.add_flow(SemiMonthlyWages("Payroll", 4000, "2012-01-01"))
    assert(c.cash_at_date("2012-01-01", "2012-02-15") == 499207.33)
    c.add_flow(SemiMonthlyWages("Payroll", -4000, "2012-01-01"))

    print(c)
    c.cash_monthly_summary("2012-01-01", "2012-07-01")
