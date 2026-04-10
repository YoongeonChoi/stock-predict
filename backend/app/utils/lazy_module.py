from __future__ import annotations

from importlib import import_module
from types import ModuleType


class LazyModuleProxy:
    """Import a module only when one of its attributes is actually accessed."""

    def __init__(self, module_name: str) -> None:
        self._lazy_module_name = module_name
        self._lazy_module: ModuleType | None = None

    def _resolve(self) -> ModuleType:
        module = self._lazy_module
        if module is None:
            module = import_module(self._lazy_module_name)
            self._lazy_module = module
        return module

    def __getattr__(self, item: str):
        return getattr(self._resolve(), item)

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(dir(self._resolve())))

    def __repr__(self) -> str:
        loaded = self._lazy_module is not None
        return f"<LazyModuleProxy module={self._lazy_module_name!r} loaded={loaded}>"
