import asyncio
import json
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

        print(
            f"[PORTAL] INIT login={login!r} "
            f"has_password={bool(password)} "
            f"has_session={bool(session_cookie)} "
            f"timeout={timeout}",
            flush=True,
        )

        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout),
            cookie_jar=aiohttp.CookieJar(quote_cookie=False),
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": (
                    "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
                ),
                "Accept": "*/*",
            },
        )

        print(
            f"[PORTAL] SESSION CREATED "
            f"closed={self.session.closed}",
            flush=True,
        )

        if session_cookie:
            self._set_session_cookie(session_cookie)

    def _mask_cookie(self, value: str | None) -> str:
        if not value:
            return "<none>"

        if len(value) <= 10:
            return "***"

        return f"{value[:5]}...{value[-5:]}"

    def _dump_cookie_jar(self, prefix: str = "") -> None:
        try:
            cookies = list(self.session.cookie_jar)

            print(
                f"[PORTAL] {prefix}COOKIE JAR: "
                f"count={len(cookies)}",
                flush=True,
            )

            for cookie in cookies:
                print(
                    f"[PORTAL] {prefix}COOKIE: "
                    f"name={cookie.key!r} "
                    f"value={self._mask_cookie(cookie.value)!r} "
                    f"domain={cookie['domain']!r} "
                    f"path={cookie['path']!r} "
                    f"secure={cookie['secure']!r}",
                    flush=True,
                )

        except Exception as error:
            print(
                f"[PORTAL] {prefix}COOKIE JAR ERROR: "
                f"{type(error).__name__}: {error}",
                flush=True,
            )

    def _set_session_cookie(self, value: str) -> None:
        print(
            "[PORTAL] SET SESSION COOKIE: "
            f"value={self._mask_cookie(value)!r}",
            flush=True,
        )

        self.session.cookie_jar.update_cookies(
            {"session": value},
            response_url=aiohttp.client_reqrep.URL(BASE_URL),
        )

        self._dump_cookie_jar("AFTER SET: ")

    async def close(self) -> None:
        print("[PORTAL] CLOSE", flush=True)

        if not self.session.closed:
            await self.session.close()

        print(
            f"[PORTAL] CLOSED closed={self.session.closed}",
            flush=True,
        )

    async def check_availability(self) -> bool:
        print(
            f"[PORTAL] AVAILABILITY CHECK: GET {BASE_URL}",
            flush=True,
        )

        try:
            async with self.session.get(
                BASE_URL,
                allow_redirects=True,
            ) as response:

                print(
                    "[PORTAL] AVAILABILITY RESPONSE: "
                    f"status={response.status} "
                    f"url={response.url} "
                    f"history={[r.status for r in response.history]}",
                    flush=True,
                )

                return response.status < 500

        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
        ) as error:

            print(
                "[PORTAL] AVAILABILITY ERROR: "
                f"{type(error).__name__}: {error}",
                flush=True,
            )

            return False

    async def login_portal(self) -> str:
        if not self.password:
            raise AuthenticationError("Password required")

        print(
            f"[PORTAL] LOGIN START: "
            f"login={self.login!r} "
            f"url={LOGIN_URL}",
            flush=True,
        )

        try:
            self.session.cookie_jar.clear()

            login_data = {
                "httpd_username": self.login,
                "httpd_password": self.password,
            }

            async with self.session.post(
                LOGIN_URL,
                data=login_data,
                headers={
                    "Origin": BASE_URL,
                    "Referer": f"{BASE_URL}/",
                    "User-Agent": USER_AGENT,
                },
                allow_redirects=False,
            ) as response:

                print(
                    "[PORTAL] LOGIN RESPONSE: "
                    f"status={response.status} "
                    f"url={response.url} "
                    f"location={response.headers.get('Location')!r}",
                    flush=True,
                )

                set_cookies = response.headers.getall(
                    "Set-Cookie",
                    [],
                )

                print(
                    "[PORTAL] LOGIN SET-COOKIE COUNT: "
                    f"{len(set_cookies)}",
                    flush=True,
                )

                for index, cookie_header in enumerate(set_cookies):
                    cookie_preview = cookie_header

                    if "session=" in cookie_preview:
                        prefix, rest = cookie_preview.split(
                            "session=",
                            1,
                        )

                        cookie_preview = (
                            prefix
                            + "session=***"
                            + (
                                ";"
                                + rest.split(";", 1)[1]
                                if ";" in rest
                                else ""
                            )
                        )

                    if len(cookie_preview) > 200:
                        cookie_preview = cookie_preview[:200] + "..."

                    print(
                        f"[PORTAL] SET-COOKIE[{index}]: "
                        f"{cookie_preview}",
                        flush=True,
                    )

                self._dump_cookie_jar("LOGIN RESPONSE: ")

                if response.status not in (200, 302):
                    raise AuthenticationError(
                        f"Login failed: HTTP {response.status}"
                    )

                session_cookie = None

                for cookie in self.session.cookie_jar:
                    if cookie.key == "session":
                        session_cookie = cookie.value
                        break

                if not session_cookie:
                    cookie = SimpleCookie()

                    for value in set_cookies:
                        cookie.load(value)

                    if "session" in cookie:
                        session_cookie = cookie["session"].value

                if not session_cookie:
                    raise AuthenticationError(
                        "Session cookie not returned"
                    )

                self.session_cookie = session_cookie

                print(
                    "[PORTAL] LOGIN SUCCESS: "
                    f"session={self._mask_cookie(session_cookie)!r}",
                    flush=True,
                )

                return session_cookie

        except AuthenticationError:
            raise

        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
        ) as error:

            print(
                "[PORTAL] LOGIN NETWORK ERROR: "
                f"{type(error).__name__}: {error}",
                flush=True,
            )

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
            raise SessionExpiredError("No session")

        url = f"{BASE_URL}{path}"

        for attempt in range(2):
            print(
                "[PORTAL] REQUEST: "
                f"{method} {url} "
                f"attempt={attempt + 1}/2 "
                f"session={self._mask_cookie(self.session_cookie)}",
                flush=True,
            )

            try:
                response = await self.session.request(
                    method,
                    url,
                    json=json_data,
                    headers={
                        "Origin": BASE_URL,
                        "Referer": INTERNAL_REFERER,
                        "User-Agent": USER_AGENT,
                        "Accept": "*/*",
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

            print(
                "[PORTAL] RESPONSE: "
                f"status={response.status} "
                f"url={response.url} "
                f"location={response.headers.get('Location')!r} "
                f"content_type={response.headers.get('Content-Type')!r}",
                flush=True,
            )

            if response.status in (
                301,
                302,
                303,
                307,
                308,
                401,
                403,
            ):
                body = await response.text()

                print(
                    "[PORTAL] AUTH REDIRECT: "
                    f"status={response.status} "
                    f"body={body[:300]!r}",
                    flush=True,
                )

                response.release()

                if attempt == 0:
                    if not self.password:
                        raise SessionExpiredError(
                            "Portal session expired"
                        )

                    print(
                        "[PORTAL] RE-LOGIN",
                        flush=True,
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

            print(
                "[PORTAL] REQUEST SUCCESS: "
                f"{method} {path} HTTP {response.status}",
                flush=True,
            )

            return response

        raise PortalError("Request failed")

    async def _json_response(
        self,
        response: aiohttp.ClientResponse,
    ) -> Any:

        try:
            text = await response.text()

            try:
                return json.loads(text)

            except json.JSONDecodeError as error:
                raise PortalError(
                    "Portal API returned invalid JSON: "
                    f"{text[:300]!r}"
                ) from error

        finally:
            response.release()

    async def get_schedule(
        self,
        teacher_uid: str,
        start: str,
        end: str,
    ) -> list[dict]:

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

        data = await self._json_response(response)

        if not isinstance(data, list):
            raise PortalError(
                "Schedule API returned invalid data"
            )

        return data

    async def get_teacher_list(self) -> dict:
        response = await self._request(
            "GET",
            "/internal/teacherList.php",
        )

        data = await self._json_response(response)

        if not isinstance(data, dict):
            raise PortalError(
                "Teacher list API returned invalid data"
            )

        return data

    async def get_static_events(self) -> list[dict]:
        response = await self._request(
            "GET",
            "/internal/static.json",
        )

        data = await self._json_response(response)

        if not isinstance(data, list):
            raise PortalError(
                "Static events API returned invalid data"
            )

        return data

    async def get_teacher_info(self) -> dict:
        response = await self._request(
            "GET",
            "/internal/teacherInfo.php",
        )

        data = await self._json_response(response)

        if not isinstance(data, dict):
            raise PortalError(
                "Teacher info API returned invalid data"
            )

        return data

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

        data = await self._json_response(response)

        if not isinstance(data, list):
            raise PortalError(
                "Attendance API returned invalid data"
            )

        return data

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

        text = await response.text()
        response.release()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text