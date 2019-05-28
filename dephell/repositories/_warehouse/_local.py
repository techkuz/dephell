# built-in
import re
from datetime import datetime
from hashlib import sha256
from logging import getLogger
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# external
import attr
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

# app
from ...cache import TextCache
from ...config import config
from ...constants import ARCHIVE_EXTENSIONS
from ...models.release import Release
from ._base import WarehouseBaseRepo


logger = getLogger('dephell.repositories.warehouse.simple')
REX_WORD = re.compile('[a-zA-Z]+')


@attr.s()
class WarehouseLocalRepo(WarehouseBaseRepo):
    name = attr.ib(type=str)
    path = attr.ib(type=str)

    prereleases = attr.ib(type=bool, factory=lambda: config['prereleases'])  # allow prereleases
    propagate = True  # deps of deps will inherit repo

    def get_releases(self, dep) -> tuple:

        releases_info = dict()
        for path in Path(self.path).glob('**/*'):
            if not path.name.endswith(ARCHIVE_EXTENSIONS):
                continue
            name, version = self._parse_name(path.name)
            if canonicalize_name(name) != dep.name:
                continue
            if not version:
                continue

            if version not in releases_info:
                releases_info[version] = []
            releases_info[version].append(self._get_hash(path=path))

        # init releases
        releases = []
        prereleases = []
        for version, hashes in releases_info.items():
            # ignore version if no files for release
            release = Release(
                raw_name=dep.raw_name,
                version=version,
                time=datetime.fromtimestamp(path.stat().st_mtime),
                hashes=hashes,
                extra=dep.extra,
            )

            # filter prereleases if needed
            if release.version.is_prerelease:
                prereleases.append(release)
                if not self.prereleases and not dep.prereleases:
                    continue

            releases.append(release)

        # special case for black: if there is no releases, but found some
        # prereleases, implicitly allow prereleases for this package
        if not release and prereleases:
            releases = prereleases

        releases.sort(reverse=True)
        return tuple(releases)

    async def get_dependencies(self, name: str, version: str,
                               extra: Optional[str] = None) -> Tuple[Requirement, ...]:
        cache = TextCache('localhost', 'deps', name, str(version))
        cache
        ...

    def search(self, query: Iterable[str]) -> List[Dict[str, str]]:
        raise NotImplementedError

    @staticmethod
    def _get_hash(path: Path) -> str:
        digest = sha256()
        with path.open('rb') as stream:
            for byte_block in iter(lambda: stream.read(4096), ''):
                digest.update(byte_block)
        return digest.hexdigest()