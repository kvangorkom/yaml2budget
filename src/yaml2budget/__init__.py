"""pbudget: static HTML viewers for hierarchical performance budgets."""
from .budget import *                                        # noqa: F401,F403
from .budget import __all__ as _budget_all

__version__ = '0.1.0'
__all__ = [*_budget_all, '__version__']
