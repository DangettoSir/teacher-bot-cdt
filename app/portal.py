import asyncio
from http.cookies import SimpleCookie
from typing import Any

import aiohttp


BASE_URL = "https://teachers.it-college.ru"


class PortalError(Exception):
    pass


class PortalUnavailableError(PortalError):
    pass


class AuthenticationError(PortalError):
    pass


class SessionExpiredError(PortalError):
    pass


class TeacherPortal:
    def __init__(
        self,
        login: str,
        password: str | None = None,
        session_cookie: str | None = None,
        timeout: int = 20,
    ):
        self.login = login
        self.password = password
        self.session_cookie = session_cookie

        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers={
                "User-Agent": "TeacherScheduleBot/1.0",
            },
        )

    async def close(self):
        await self.session.close()

    async def check_availability(
        self,
    ) -> bool:
        try:
            async with self.session.get(
                BASE_URL,
                allow_redirects=True,
            ) as response:
                return response.status < 500

        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
        ):
            return False

    async def login_portal(self) -> str:
        if not self.password:
            raise AuthenticationError(
                "Password required"
            )

        try:
            async with self.session.post(
                f"{BASE_URL}/dologin.html",
                data={
                    "httpd_username": self.login,
                    "httpd_password": self.password,
                },
                allow_redirects=False,
            ) as response:

                if response.status not in (
                    301,
                    302,
                    303,
                    307,
                    308,
                ):
                    raise AuthenticationError(
                        f"Login failed: HTTP {response.status}"
                    )

                cookies = response.headers.getall(
                    "Set-Cookie",
                    [],
                )

                cookie = SimpleCookie()

                for value in cookies:
                    cookie.load(value)

                if "session" not in cookie:
                    raise AuthenticationError(
                        "Session cookie not returned"
                    )

                self.session_cookie = (
                    cookie["session"].value
                )

                return self.session_cookie

        except aiohttp.ClientError as error:
            raise PortalUnavailableError(
                "Portal unavailable"
            ) from error

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_data: Any = None,
    ):
        if not self.session_cookie:
            raise SessionExpiredError(
                "No session"
            )

        try:
            response = await self.session.request(
                method,
                f"{BASE_URL}{path}",
                json=json_data,
                cookies={
                    "session": self.session_cookie,
                },
                allow_redirects=False,
            )

        except (
            aiohttp.ClientError,
            TimeoutError,
        ) as error:
            raise PortalUnavailableError(
                "Portal unavailable"
            ) from error

        if response.status in (
            301,
            302,
            303,
            307,
            308,
            401,
            403,
        ):
            response.release()

            raise SessionExpiredError(
                "Portal session expired"
            )

        if response.status >= 500:
            response.release()

            raise PortalUnavailableError(
                "Portal unavailable"
            )

        if response.status != 200:
            text = await response.text()

            response.release()

            raise PortalError(
                f"Portal returned HTTP "
                f"{response.status}: {text[:200]}"
            )

        return response

    async def get_schedule(
        self,
        teacher_uid: str,
        start: str,
        end: str,
    ) -> list[dict]:
        response = await self._request(
            "POST",
            "/internal/tschedule26.php",
            json_data={
                "d_start": start,
                "d_end": end,
                "teacher": teacher_uid,
            },
        )

        try:
            return await response.json()
        finally:
            response.release()