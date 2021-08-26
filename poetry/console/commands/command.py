from typing import TYPE_CHECKING
from typing import Optional

from cleo.commands.command import Command as BaseCommand


if TYPE_CHECKING:
    from poetry.console.application import Application
    from poetry.poetry import Poetry


class Command(BaseCommand):
    loggers = []

    _poetry: Optional["Poetry"] = None

    @property
    def poetry(self) -> "Poetry":
        if self._poetry is None:
            self._poetry = self.get_application().poetry

        return self._poetry

    def set_poetry(self, poetry: "Poetry") -> None:
        self._poetry = poetry

    def get_application(self) -> "Application":
        return self.application

    def reset_poetry(self) -> None:
        self.get_application().reset_poetry()
