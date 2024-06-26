from collections.abc import Iterator
from contextlib import contextmanager
import os
import shutil
from typing import Callable, Literal
from pyndex import server, Pyndex
from litestar.testing import TestClient
from httpx import BasicAuth
import pytest
from litestar import Litestar
from pydantic import BaseModel


class UserRequest(BaseModel):
    type: Literal["user"] = "user"
    username: str
    password: str | None = None
    groups: list[str] = []
    server_permissions: list[Literal["meta.admin", "meta.create"]] = []
    package_permissions: list[
        tuple[str, Literal["pkg.manage", "pkg.edit", "pkg.view"]]
    ] = []


class GroupRequest(BaseModel):
    type: Literal["group"] = "group"
    name: str
    display_name: str | None = None
    server_permissions: list[Literal["meta.admin", "meta.create"]] = []
    package_permissions: list[
        tuple[str, Literal["pkg.manage", "pkg.edit", "pkg.view"]]
    ] = []


class PackageRequest(BaseModel):
    type: Literal["package"] = "package"
    dist: str
    username: str | None = None
    password: str | None = None


class Requests(BaseModel):
    user: list[UserRequest] = []
    group: list[GroupRequest] = []
    package: list[PackageRequest] = []

    def append(self, request: UserRequest | GroupRequest | PackageRequest):
        getattr(self, request.type).append(request)


USERNAME_ADMIN = "admin"
PASSWORD_ADMIN = "admin"


@pytest.fixture(scope="class", autouse=True)
def env(tmp_path_factory: pytest.TempPathFactory, request):
    requests = Requests()
    for request_type in ["user", "group", "package"]:
        for req in request.node.iter_markers(name=request_type):
            match request_type:
                case "user":
                    requests.append(UserRequest(**req.kwargs))
                case "group":
                    requests.append(GroupRequest(**req.kwargs))
                case "package":
                    requests.append(PackageRequest(**req.kwargs))

    directory = tmp_path_factory.mktemp("pynd_base")
    shutil.copyfile("./config.toml", "config.toml.dev")
    shutil.copyfile("./config.test.toml", "./config.toml")
    with open("config.toml", "r") as f:
        contents = f.read()
    (directory / "storage").mkdir(exist_ok=True)
    storage = (directory / "storage").absolute()

    with open("config.toml", "w") as f:
        f.write(contents.replace("{storage}", str(storage)))

    with TestClient(app=server) as client:
        client.auth = BasicAuth(username=USERNAME_ADMIN, password=PASSWORD_ADMIN)
        with Pyndex("http://testserver.local").session(client=client) as index:
            for group in requests.group:
                index.groups.create(group.name, display_name=group.display_name)

                for perm in group.server_permissions:
                    client.post(
                        f"/groups/name/{group.name}/permissions",
                        json={"permission": perm},
                    )

                for perm in group.package_permissions:
                    client.post(
                        f"/groups/name/{group.name}/permissions",
                        json={"permission": perm[1], "project": perm[0]},
                    )

            for user in requests.user:
                created = index.users.create(user.username, password=user.password)
                for group in user.groups:
                    client.post(
                        f"/groups/name/{group}/members",
                        params={"auth_type": "user", "auth_id": created.id},
                    )

                for perm in user.server_permissions:
                    client.post(
                        f"/users/name/{user.username}/permissions",
                        json={"permission": perm},
                    )

                for perm in user.package_permissions:
                    client.post(
                        f"/users/name/{user.username}/permissions",
                        json={"permission": perm[1], "project": perm[0]},
                    )

    for package in requests.package:
        with TestClient(app=server) as client:
            client.auth = BasicAuth(
                username=package.username if package.username else "",
                password=package.password if package.password else "",
            )
            with Pyndex(
                "http://testserver.local",
                username=package.username,
                password=package.password,
            ).session(client=client) as index:
                index.package.upload(package.dist)

    yield directory
    shutil.copyfile("config.toml.dev", "config.toml")
    os.remove("config.toml.dev")


@pytest.fixture(scope="function")
def admin_client(env) -> Iterator[TestClient[Litestar]]:
    with TestClient(app=server) as client:
        client.auth = BasicAuth(username=USERNAME_ADMIN, password=PASSWORD_ADMIN)
        yield client


@pytest.fixture(scope="function")
def as_admin(admin_client: TestClient) -> Iterator[Pyndex]:
    with Pyndex(
        "http://testserver.local", username=USERNAME_ADMIN, password=PASSWORD_ADMIN
    ).session(client=admin_client) as session:
        yield session


@pytest.fixture(scope="function")
def user_client(env) -> Callable[[str, str | None], Iterator[TestClient[Litestar]]]:
    @contextmanager
    def make_client(
        username: str, password: str | None
    ) -> Iterator[TestClient[Litestar]]:
        with TestClient(app=server) as client:
            client.auth = BasicAuth(
                username=username, password=password if password else None
            )
            yield client

    return make_client


@pytest.fixture(scope="function")
def as_user(env, user_client) -> Callable[[str, str | None], Iterator[Pyndex]]:
    @contextmanager
    def make_index(
        username: str, password: str | None
    ) -> Iterator[TestClient[Litestar]]:
        with user_client(username, password) as client:
            with Pyndex(
                "http://testserver.local", username=username, password=password
            ).session(client=client) as index:
                yield index

    return make_index


@pytest.fixture
def admin_creds() -> tuple[str, str]:
    return USERNAME_ADMIN, PASSWORD_ADMIN
