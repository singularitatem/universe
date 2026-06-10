from abc import ABC, ABCMeta, abstractmethod
from typing import Any

class Cache(ABC, metaclass=ABCMeta):

    @abstractmethod
    def set(self, key: Any, value: Any):
        pass

    @abstractmethod
    def get(self, key: Any) -> Any:
        pass

    @abstractmethod
    def reset(self, capacity) -> None:
        pass