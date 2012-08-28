from django.db import models
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.models.sql.compiler import SQLCompiler
from typing_extensions import override


@models.Field.register_lookup
class AndZero(models.Lookup[int]):
    lookup_name = "andz"

    @override
    def as_sql(
        self, compiler: SQLCompiler, connection: BaseDatabaseWrapper
    ) -> tuple[str, list[str | int]]:  # nocoverage # currently only used in migrations
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        return f"{lhs} & {rhs} = 0", [*lhs_params, *rhs_params]


@models.Field.register_lookup
class AndNonZero(models.Lookup[int]):
    lookup_name = "andnz"

    @override
    def as_sql(
        self, compiler: SQLCompiler, connection: BaseDatabaseWrapper
    ) -> tuple[str, list[str | int]]:  # nocoverage # currently only used in migrations
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        return f"{lhs} & {rhs} != 0", [*lhs_params, *rhs_params]
