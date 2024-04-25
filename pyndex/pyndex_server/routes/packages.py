from typing import Optional
from httpx import AsyncClient
from litestar import Controller, Request, get
from litestar.exceptions import *
from ..context import Context
from ..models import Package, FileMetadata


class PackagesController(Controller):
    path = "/packages"

    @get("/{project_name:str}")
    async def get_package(
        self,
        context: Context,
        project_name: str,
        request: Request,
        local: Optional[bool] = False,
    ) -> Package:
        try:
            return Package.assemble_package(
                context.root.joinpath("index", project_name), url_base=request.base_url
            )
        except FileNotFoundError:
            if len(context.config.proxies) > 0:
                for proxy in context.config.proxies:
                    if proxy.urls.package:
                        async with AsyncClient(follow_redirects=True) as client:
                            result = await client.get(
                                proxy.urls.package.format(project_name=project_name)
                            )
                            if result.is_success:
                                return Package(**result.json(), local=False)
            raise NotFoundException("Unknown package.")