from __future__ import annotations

from odoo.osv import expression


class Domain(list):
    """Small stand-in for the ``Domain`` class that Odoo ships from 19.0 on.

    It only covers what this module needs: building a domain from a list or a
    single condition, combining with ``&``, ``|`` and ``~``, and validating it
    against a model. Since it is a plain list, it can go straight into
    ``search()`` and friends.
    """

    TRUE: Domain
    FALSE: Domain

    def __init__(self, *args) -> None:
        if len(args) == 3:
            super().__init__([tuple(args)])
        elif len(args) == 1 and args[0]:
            super().__init__(expression.normalize_domain(list(args[0])))
        elif len(args) <= 1:
            super().__init__()
        else:
            raise TypeError(f"Domain() takes a domain or a (field, operator, value) condition, got {args!r}")

    def is_true(self) -> bool:
        return not self or list(self) == [expression.TRUE_LEAF]

    def is_false(self) -> bool:
        return list(self) == [expression.FALSE_LEAF]

    def __and__(self, other) -> Domain:
        return Domain(expression.AND([self, Domain(other)]))

    def __or__(self, other) -> Domain:
        return Domain(expression.OR([self, Domain(other)]))

    def __invert__(self) -> Domain:
        if self.is_true():
            return Domain([expression.FALSE_LEAF])
        if self.is_false():
            return Domain()
        return Domain(['!', *self])

    def validate(self, model) -> None:
        expression.expression(list(self), model)

    def __repr__(self) -> str:
        return f"Domain({list(self)!r})"


Domain.TRUE = Domain()
Domain.FALSE = Domain([expression.FALSE_LEAF])
