from logging import getLogger
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Tuple

from aiohttp import ClientSession
from dephell_markers import Markers
from packaging.requirements import InvalidRequirement, Requirement

from ..base import Interface


try:
    import aiofiles
except ImportError:
    aiofiles = None


logger = getLogger('dephell.repositories.warehouse')


class BaseWarehouse(Interface):

    @staticmethod
    def _convert_deps(deps, name, version, extra):

        # filter result
        result = []
        for dep in deps:
            try:
                req = Requirement(dep)
            except InvalidRequirement as e:
                msg = 'cannot parse requirement: {} from {} {}'
                try:
                    # try to parse with dropped out markers
                    req = Requirement(dep.split(';')[0])
                except InvalidRequirement:
                    raise ValueError(msg.format(dep, name, version)) from e
                else:
                    logger.warning('cannot parse marker', extra=dict(
                        requirement=dep,
                        source_name=name,
                        source_version=version,
                    ))

            try:
                dep_extra = req.marker and Markers(req.marker).extra
            except ValueError:  # unsupported operation for version marker python_version: in
                dep_extra = None

            # it's not extra and we want not extra too
            if dep_extra is None and extra is None:
                result.append(req)
                continue
            # it's extra, but we want not the extra
            # or it's not the extra, but we want extra.
            if dep_extra is None or extra is None:
                continue
            # it's extra and we want this extra
            elif dep_extra == extra:
                result.append(req)
                continue

        return tuple(result)

    async def _download_and_parse(self, *, url: str, converter) -> Tuple[str, ...]:
        with TemporaryDirectory() as tmp:
            async with ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise ValueError('invalid response: {} {} ({})'.format(
                            response.status, response.reason, url,
                        ))
                    path = Path(tmp) / url.rsplit('/', maxsplit=1)[-1]

                    # download file
                    if aiofiles is not None:
                        async with aiofiles.open(str(path), mode='wb') as stream:
                            while True:
                                chunk = await response.content.read(1024)
                                if not chunk:
                                    break
                                await stream.write(chunk)
                    else:
                        with path.open(mode='wb') as stream:
                            while True:
                                chunk = await response.content.read(1024)
                                if not chunk:
                                    break
                                stream.write(chunk)

            # load and make separated dep for every env
            root = converter.load(path)
            deps = []
            for dep in root.dependencies:
                for env in dep.envs.copy():
                    dep.envs = {env}
                    deps.append(str(dep))
            return tuple(deps)