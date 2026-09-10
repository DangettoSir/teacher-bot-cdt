import asyncio
from http.cookies import SimpleCookie
from typing import Any

import aiohttp


BASE_URL = "https://teachers.it-college.ru"
LOGIN_URL = f"{BASE_URL}/dologin.html"
INTERNAL_REFERER = f"{BASE_URL}/internal/s.shtml"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36"
)


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
                "User-Agent": USER_AGENT,
                "Accept-Language": (
                    "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
                ),
            },
        )

        if session_cookie:
            self._set_session_cookie(session_cookie)

    def _set_session_cookie(self, value: str) -> None:
        self.session.cookie_jar.update_cookies(
            {"session": value},
            response_url=aiohttp.client_reqrep.URL(BASE_URL),
        )

    async def close(self) -> None:
        if not self.session.closed:
            await self.session.close()

    async def check_availability(self) -> bool:
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
            # mod_auth_form может не выдать новую cookie,
            # если старая session ещё присутствует.
            self.session.cookie_jar.clear()

            async with self.session.post(
                LOGIN_URL,
                data={
                    "httpd_username": self.login,
                    "httpd_password": self.password,
                },
                headers={
                    "Origin": BASE_URL,
                    "Referer": f"{BASE_URL}/",
                },
                allow_redirects=False,
            ) as response:

                if response.status not in (200, 302):
                    raise AuthenticationError(
                        f"Login failed: HTTP {response.status}"
                    )

                # Сначала пробуем получить cookie из cookie jar.
                session_cookie = None

                for cookie in self.session.cookie_jar:
                    if cookie.key == "session":
                        session_cookie = cookie.value
                        break

                # Если cookie jar её не сохранил,
                # пытаемся разобрать Set-Cookie вручную.
                if not session_cookie:
                    cookies = response.headers.getall(
                        "Set-Cookie",
                        [],
                    )

                    cookie = SimpleCookie()

                    for value in cookies:
                        cookie.load(value)

                    if "session" in cookie:
                        session_cookie = (
                            cookie["session"].value
                        )

                if not session_cookie:
                    raise AuthenticationError(
                        "Session cookie not returned"
                    )

                self.session_cookie = session_cookie

                return session_cookie

        except AuthenticationError:
            raise

        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
        ) as error:
            raise PortalUnavailableError(
                "Portal unavailable"
            ) from error

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_data: Any = None,
    ) -> aiohttp.ClientResponse:

        if not self.session_cookie:
            raise SessionExpiredError(
                "No session"
            )

        for attempt in range(2):
            try:
                response = await self.session.request(
                    method,
                    f"{BASE_URL}{path}",
                    json=json_data,
                    cookies={
                        "session": self.session_cookie,
                    },
                    headers={
                        "Origin": BASE_URL,
                        "Referer": INTERNAL_REFERER,
                    },
                    allow_redirects=False,
                )

            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
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

                if attempt == 0:
                    if not self.password:
                        raise SessionExpiredError(
                            "Portal session expired"
                        )

                    await self.login_portal()
                    continue

                raise SessionExpiredError(
                    "Portal session expired"
                )

            if response.status >= 500:
                response.release()

                raise PortalUnavailableError(
                    f"Portal returned HTTP {response.status}"
                )

            if response.status != 200:
                text = await response.text()
                response.release()

                raise PortalError(
                    f"Portal returned HTTP "
                    f"{response.status}: {text[:200]}"
                )

            return response

        raise PortalError("Request failed")

    async def get_schedule(
        self,
        teacher_uid: str,
        start: str,
        end: str,
    ) -> list[dict]:

        # API ожидает datetime:
        # 2026-09-07T00:00:00.000Z
        if len(start) == 10:
            start = f"{start}T00:00:00.000Z"

        if len(end) == 10:
            end = f"{end}T00:00:00.000Z"

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
            data = await response.json()

            if not isinstance(data, list):
                raise PortalError(
                    "Schedule API returned invalid data"
                )

            return data

        except aiohttp.ContentTypeError as error:
            text = await response.text()

            raise PortalError(
                "Schedule API returned non-JSON body: "
                f"{text[:200]!r}"
            ) from error

        finally:
            response.release()

    async def get_teacher_list(self) -> dict:
        response = await self._request(
            "GET",
            "/internal/teacherList.php",
        )

        try:
            return await response.json()
        finally:
            response.release()

    async def get_static_events(self) -> list[dict]:
        response = await self._request(
            "GET",
            "/internal/static.json",
        )

        try:
            return await response.json()
        finally:
            response.release()

    async def get_teacher_info(self) -> dict:
        response = await self._request(
            "GET",
            "/internal/teacherInfo.php",
        )

        try:
            return await response.json()
        finally:
            response.release()

    async def get_attendance(
        self,
        pr_id: str,
        day: str,
        para_n: str,
    ) -> list[dict]:

        response = await self._request(
            "POST",
            "/internal/tattn26.php",
            json_data={
                "PrID": pr_id,
                "Day": day,
                "ParaN": para_n,
            },
        )

        try:
            data = await response.json()

            if not isinstance(data, list):
                raise PortalError(
                    "Attendance API returned invalid data"
                )

            return data

        finally:
            response.release()

    async def register_attendance(
        self,
        cl_id: str,
        scl_id: str,
        stdlist: dict[str, str],
        pr_id: str,
    ) -> Any:

        response = await self._request(
            "POST",
            "/internal/attnreg26.php",
            json_data={
                "ClID": cl_id,
                "SClID": scl_id,
                "stdlist": stdlist,
                "PrID": pr_id,
            },
        )

        try:
            return await response.json()

        except aiohttp.ContentTypeError:
            return await response.text()

        finally:
            response.release()
