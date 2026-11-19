from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    gb: int
    price: int
    days: int = 30


PLANS = {
    plan.gb: plan
    for plan in (
        Plan(10, 120_000), Plan(20, 230_000), Plan(30, 340_000),
        Plan(40, 450_000), Plan(50, 560_000), Plan(80, 880_000),
        Plan(120, 1_260_000),
    )
}
SERVER = "سرور اصلی"
