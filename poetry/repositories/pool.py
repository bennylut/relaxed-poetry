from typing import TYPE_CHECKING
from typing import Dict
from typing import List
from typing import Optional

from .base_repository import BaseRepository
from .exceptions import PackageNotFound
from .repository import Repository

if TYPE_CHECKING:
    from poetry.core.packages.dependency import Dependency
    from poetry.core.packages.package import Package
    from ..managed_project import ManagedProject


class Pool(BaseRepository):
    def __init__(
            self,
            repositories: Optional[List[Repository]] = None,
            ignore_repository_names: bool = False,
            parent: Optional["Pool"] = None,
    ) -> None:
        if repositories is None:
            repositories = []

        self._lookup: Dict[str, int] = {}
        self._repositories: List[Repository] = []
        self._default = False
        self._has_primary_repositories = False
        self._secondary_start_idx = None
        self._parent = parent

        for repository in repositories:
            self.add_repository(repository)

        self._ignore_repository_names = ignore_repository_names

        super().__init__()

    @property
    def repositories(self) -> List[Repository]:
        return self._repositories

    def has_default(self) -> bool:
        return self._default

    def has_primary_repositories(self) -> bool:
        return self._has_primary_repositories

    def has_repository(self, name: str) -> bool:
        name = name.lower() if name is not None else None

        return name in self._lookup

    def repository(self, name: str) -> Repository:
        if name is not None:
            name = name.lower()

        if name in self._lookup:
            return self._repositories[self._lookup[name]]

        raise ValueError(f'Repository "{name}" does not exist.')

    def add_repository(
            self, repository: Repository, default: bool = False, secondary: bool = False
    ) -> "Pool":
        """
        Adds a repository to the pool.
        """
        repository_name = (
            repository.name.lower() if repository.name is not None else None
        )
        if default:
            if self.has_default():
                raise ValueError("Only one repository can be the default")

            self._default = True
            self._repositories.insert(0, repository)
            for name in self._lookup:
                self._lookup[name] += 1

            if self._secondary_start_idx is not None:
                self._secondary_start_idx += 1

            self._lookup[repository_name] = 0
        elif secondary:
            if self._secondary_start_idx is None:
                self._secondary_start_idx = len(self._repositories)

            self._repositories.append(repository)
            self._lookup[repository_name] = len(self._repositories) - 1
        else:
            self._has_primary_repositories = True
            if self._secondary_start_idx is None:
                self._repositories.append(repository)
                self._lookup[repository_name] = len(self._repositories) - 1
            else:
                self._repositories.insert(self._secondary_start_idx, repository)

                for name, idx in self._lookup.items():
                    if idx < self._secondary_start_idx:
                        continue

                    self._lookup[name] += 1

                self._lookup[repository_name] = self._secondary_start_idx
                self._secondary_start_idx += 1

        return self

    def remove_repository(self, repository_name: str) -> "Pool":
        if repository_name is not None:
            repository_name = repository_name.lower()

        idx = self._lookup.get(repository_name)
        if idx is not None:
            del self._repositories[idx]

        return self

    def has_package(self, package: "Package") -> bool:
        raise NotImplementedError()

    def package(
            self, name: str, version: str, project: "ManagedProject", extras: List[str] = None, repository: str = None
    ) -> "Package":
        from poetry.managed_project import ManagedProject
        if not isinstance(project, ManagedProject):
            raise RuntimeError("HERE: ")

        if repository is not None:
            repository = repository.lower()

        if (
                repository is not None
                and repository not in self._lookup
                and not self._ignore_repository_names
        ):
            if self._parent:
                return self._parent.package(name, version, project, extras, repository)
            raise ValueError(f'Repository "{repository}" does not exist.')

        if repository is not None and not self._ignore_repository_names:
            try:
                return self.repository(repository).package(name, version, project, extras=extras)
            except PackageNotFound:
                pass
        else:
            for repo in self._repositories:
                try:
                    package = repo.package(name, version, project, extras=extras)
                except PackageNotFound:
                    continue

                if package:
                    self._packages.append(package)

                    return package

        if self._parent:
            return self._parent.package(name, version, project, extras, repository)
        raise PackageNotFound(f"Package {name} ({version}) not found.")

    def find_packages(self, dependency: "Dependency") -> List["Package"]:
        repository = dependency.source_name
        if repository is not None:
            repository = repository.lower()

        if (
                repository is not None
                and repository not in self._lookup
                and not self._ignore_repository_names
        ):
            if self._parent:
                return self._parent.find_packages(dependency)
            raise ValueError(f'Repository "{repository}" does not exist.')

        if repository is not None and not self._ignore_repository_names:
            return self.repository(repository).find_packages(dependency)

        packages = []
        for repo in self._repositories[:self._secondary_start_idx]:
            found_packages = repo.find_packages(dependency)
            if len(found_packages) > 0:
                packages += found_packages
                break

        if len(packages) == 0 and self._parent is not None:
            return self._parent.find_packages(dependency)

        return packages

    def search(self, query: str) -> List["Package"]:
        from .legacy_repository import LegacyRepository

        results = []
        for repository in self._repositories:
            if isinstance(repository, LegacyRepository):
                continue

            results += repository.search(query)

        return results + (self._parent.search(query) if self._parent else [])
