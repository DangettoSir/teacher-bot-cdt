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

        print(
            f"[PORTAL] INIT login={login!r} "
            f"has_password={bool(password)} "
            f"has_session={bool(session_cookie)} "
            f"timeout={timeout}",
            flush=True,
        )

        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": (
                    "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
                ),
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
            f"[PORTAL] SET SESSION COOKIE: "
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
                    f"[PORTAL] AVAILABILITY RESPONSE: "
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
                f"[PORTAL] AVAILABILITY ERROR: "
                f"{type(error).__name__}: {error}",
                flush=True,
            )

            return False

    async def login_portal(self) -> str:
        if not self.password:
            print(
                "[PORTAL] LOGIN ERROR: password is missing",
                flush=True,
            )

            raise AuthenticationError("Password required")

        print(
            f"[PORTAL] LOGIN START: "
            f"login={self.login!r} "
            f"url={LOGIN_URL}",
            flush=True,
        )

        try:
            print(
                "[PORTAL] LOGIN: clearing cookie jar",
                flush=True,
            )

            self.session.cookie_jar.clear()

            self._dump_cookie_jar("AFTER CLEAR: ")

            login_data = {
                "httpd_username": self.login,
                "httpd_password": self.password,
            }

            print(
                "[PORTAL] LOGIN REQUEST: "
                f"method=POST "
                f"url={LOGIN_URL} "
                f"data_keys={list(login_data.keys())} "
                f"allow_redirects=False",
                flush=True,
            )

            async with self.session.post(
                LOGIN_URL,
                data=login_data,
                headers={
                    "Origin": BASE_URL,
                    "Referer": f"{BASE_URL}/",
                },
                allow_redirects=False,
            ) as response:

                print(
                    "[PORTAL] LOGIN RESPONSE: "
                    f"status={response.status} "
                    f"url={response.url}",
                    flush=True,
                )

                print(
                    "[PORTAL] LOGIN RESPONSE HEADERS:",
                    flush=True,
                )

                for key, value in response.headers.items():
                    if key.lower() == "set-cookie":
                        print(
                            f"[PORTAL]   {key}: <hidden>",
                            flush=True,
                        )
                    else:
                        print(
                            f"[PORTAL]   {key}: {value}",
                            flush=True,
                        )

                location = response.headers.get("Location")

                print(
                    f"[PORTAL] LOGIN LOCATION: {location!r}",
                    flush=True,
                )

                set_cookies = response.headers.getall(
                    "Set-Cookie",
                    [],
                )

                print(
                    f"[PORTAL] LOGIN SET-COOKIE COUNT: "
                    f"{len(set_cookies)}",
                    flush=True,
                )

                for index, cookie_header in enumerate(set_cookies):
                    cookie_preview = cookie_header

                    if len(cookie_preview) > 150:
                        cookie_preview = (
                            cookie_preview[:150] + "..."
                        )

                    if "session=" in cookie_preview:
                        cookie_preview = (
                            cookie_preview
                            .replace(
                                cookie_preview.split(
                                    "session=", 1
                                )[1].split(";", 1)[0],
                                "***",
                                1,
                            )
                        )

                    print(
                        f"[PORTAL]   SET-COOKIE[{index}]: "
                        f"{cookie_preview}",
                        flush=True,
                    )

                body = await response.text()

                print(
                    f"[PORTAL] LOGIN BODY: "
                    f"length={len(body)} "
                    f"preview={body[:500]!r}",
                    flush=True,
                )

                print(
                    f"[PORTAL] LOGIN HISTORY: "
                    f"{[(r.status, str(r.url)) for r in response.history]}",
                    flush=True,
                )

                self._dump_cookie_jar("LOGIN RESPONSE: ")

                if response.status not in (200, 302):
                    print(
                        f"[PORTAL] LOGIN FAILED: "
                        f"unexpected HTTP {response.status}",
                        flush=True,
                    )

                    raise AuthenticationError(
                        f"Login failed: HTTP {response.status}"
                    )

                session_cookie = None

                print(
                    "[PORTAL] LOGIN: searching session "
                    "cookie in aiohttp cookie jar",
                    flush=True,
                )

                for cookie in self.session.cookie_jar:
                    print(
                        f"[PORTAL] LOGIN COOKIE FOUND: "
                        f"name={cookie.key!r} "
                        f"value={self._mask_cookie(cookie.value)!r} "
                        f"domain={cookie['domain']!r} "
                        f"path={cookie['path']!r}",
                        flush=True,
                    )

                    if cookie.key == "session":
                        session_cookie = cookie.value
                        break

                if session_cookie:
                    print(
                        "[PORTAL] LOGIN: session cookie "
                        "found in cookie jar",
                        flush=True,
                    )

                if not session_cookie:
                    print(
                        "[PORTAL] LOGIN: cookie jar has no "
                        "session cookie, parsing Set-Cookie manually",
                        flush=True,
                    )

                    cookie = SimpleCookie()

                    for value in set_cookies:
                        cookie.load(value)

                    if "session" in cookie:
                        session_cookie = (
                            cookie["session"].value
                        )

                        print(
                            "[PORTAL] LOGIN: session cookie "
                            "found in Set-Cookie manually",
                            flush=True,
                        )

                if not session_cookie:
                    print(
                        "[PORTAL] LOGIN FAILED: "
                        "server did not return session cookie",
                        flush=True,
                    )

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
                f"[PORTAL] LOGIN NETWORK ERROR: "
                f"{type(error).__name__}: {error}",
                flush=True,
            )

            raise PortalUnavailableError(
                "Portal unavailable"
            ) from error

        except Exception as error:

            print(
                f"[PORTAL] LOGIN UNKNOWN ERROR: "
                f"{type(error).__name__}: {error}",
                flush=True,
            )

            raise

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_data: Any = None,
    ) -> aiohttp.ClientResponse:

        if not self.session_cookie:
            print(
                f"[PORTAL] REQUEST BLOCKED: "
                f"{method} {path} -> no session",
                flush=True,
            )

            raise SessionExpiredError("No session")

        url = f"{BASE_URL}{path}"

        print(
            f"[PORTAL] REQUEST START: "
            f"method={method} "
            f"path={path} "
            f"attempts=2",
            flush=True,
        )

        print(
            f"[PORTAL] REQUEST URL: {url}",
            flush=True,
        )

        if json_data is not None:
            print(
                f"[PORTAL] REQUEST JSON: {json_data!r}",
                flush=True,
            )

        for attempt in range(2):
            print(
                f"[PORTAL] REQUEST ATTEMPT: "
                f"{attempt + 1}/2 "
                f"session={self._mask_cookie(self.session_cookie)!r}",
                flush=True,
            )

            try:
                response = await self.session.request(
                    method,
                    url,
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

                print(
                    f"[PORTAL] REQUEST NETWORK ERROR: "
                    f"attempt={attempt + 1} "
                    f"{type(error).__name__}: {error}",
                    flush=True,
                )

                raise PortalUnavailableError(
                    "Portal unavailable"
                ) from error

            print(
                f"[PORTAL] RESPONSE: "
                f"status={response.status} "
                f"url={response.url}",
                flush=True,
            )

            print(
                "[PORTAL] RESPONSE HEADERS:",
                flush=True,
            )

            for key, value in response.headers.items():
                if key.lower() == "set-cookie":
                    print(
                        f"[PORTAL]   {key}: <hidden>",
                        flush=True,
                    )
                else:
                    print(
                        f"[PORTAL]   {key}: {value}",
                        flush=True,
                    )

            print(
                f"[PORTAL] RESPONSE LOCATION: "
                f"{response.headers.get('Location')!r}",
                flush=True,
            )

            self._dump_cookie_jar("RESPONSE: ")

            if response.status in (
                301,
                302,
                303,
                307,
                308,
                401,
                403,
            ):

                print(
                    f"[PORTAL] AUTH FAILURE: "
                    f"status={response.status} "
                    f"location={response.headers.get('Location')!r} "
                    f"attempt={attempt + 1}/2",
                    flush=True,
                )

                try:
                    body = await response.text()

                    print(
                        f"[PORTAL] AUTH FAILURE BODY: "
                        f"length={len(body)} "
                        f"preview={body[:1000]!r}",
                        flush=True,
                    )

                except Exception as error:
                    print(
                        f"[PORTAL] AUTH FAILURE BODY ERROR: "
                        f"{type(error).__name__}: {error}",
                        flush=True,
                    )

                response.release()

                if attempt == 0:
                    if not self.password:
                        print(
                            "[PORTAL] AUTH FAILURE: "
                            "cannot re-login because password is missing",
                            flush=True,
                        )

                        raise SessionExpiredError(
                            "Portal session expired"
                        )

                    print(
                        "[PORTAL] AUTH FAILURE: "
                        "trying portal re-login",
                        flush=True,
                    )

                    await self.login_portal()

                    print(
                        "[PORTAL] RE-LOGIN SUCCESS: "
                        "retrying original request",
                        flush=True,
                    )

                    continue

                print(
                    "[PORTAL] AUTH FAILURE: "
                    "request still unauthorized after re-login",
                    flush=True,
                )

                raise SessionExpiredError(
                    "Portal session expired"
                )

            if response.status >= 500:
                print(
                    f"[PORTAL] SERVER ERROR: "
                    f"HTTP {response.status}",
                    flush=True,
                )

                try:
                    body = await response.text()

                    print(
                        f"[PORTAL] SERVER ERROR BODY: "
                        f"{body[:1000]!r}",
                        flush=True,
                    )

                finally:
                    response.release()

                raise PortalUnavailableError(
                    f"Portal returned HTTP {response.status}"
                )

            if response.status != 200:
                try:
                    text = await response.text()

                    print(
                        f"[PORTAL] UNEXPECTED STATUS: "
                        f"HTTP {response.status} "
                        f"body={text[:1000]!r}",
                        flush=True,
                    )

                finally:
                    response.release()

                raise PortalError(
                    f"Portal returned HTTP "
                    f"{response.status}: {text[:200]}"
                )

            print(
                f"[PORTAL] REQUEST SUCCESS: "
                f"{method} {path} "
                f"HTTP {response.status}",
                flush=True,
            )

            return response

        raise PortalError("Request failed")

    async def get_schedule(
        self,
        teacher_uid: str,
        start: str,
        end: str,
    ) -> list[dict]:

        print(
            f"[PORTAL] GET SCHEDULE: "
            f"teacher={teacher_uid!r} "
            f"start={start!r} "
            f"end={end!r}",
            flush=True,
        )

        if len(start) == 10:
            start = f"{start}T00:00:00.000Z"

        if len(end) == 10:
            end = f"{end}T00:00:00.000Z"

        print(
            f"[PORTAL] GET SCHEDULE NORMALIZED: "
            f"start={start!r} "
            f"end={end!r}",
            flush=True,
        )

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

            print(
                f"[PORTAL] SCHEDULE RESPONSE: "
                f"type={type(data).__name__} "
                f"items={len(data) if isinstance(data, list) else 'N/A'}",
                flush=True,
            )

            if not isinstance(data, list):
                print(
                    f"[PORTAL] SCHEDULE INVALID DATA: "
                    f"{data!r}",
                    flush=True,
                )

                raise PortalError(
                    "Schedule API returned invalid data"
                )

            return data

        except aiohttp.ContentTypeError as error:
            text = await response.text()

            print(
                f"[PORTAL] SCHEDULE NON-JSON: "
                f"{text[:1000]!r}",
                flush=True,
            )

            raise PortalError(
                "Schedule API returned non-JSON body: "
                f"{text[:200]!r}"
            ) from error

        finally:
            response.release()

    async def get_teacher_list(self) -> dict:
        print(
            "[PORTAL] GET TEACHER LIST",
            flush=True,
        )

        response = await self._request(
            "GET",
            "/internal/teacherList.php",
        )

        try:
            data = await response.json()

            print(
                f"[PORTAL] TEACHER LIST SUCCESS: "
                f"type={type(data).__name__}",
                flush=True,
            )

            return data

        finally:
            response.release()

    async def get_static_events(self) -> list[dict]:
        print(
            "[PORTAL] GET STATIC EVENTS",
            flush=True,
        )

        response = await self._request(
            "GET",
            "/internal/static.json",
        )

        try:
            data = await response.json()

            print(
                f"[PORTAL] STATIC EVENTS SUCCESS: "
                f"type={type(data).__name__} "
                f"items={len(data) if isinstance(data, list) else 'N/A'}",
                flush=True,
            )

            return data

        finally:
            response.release()

    async def get_teacher_info(self) -> dict:
        print(
            "[PORTAL] GET TEACHER INFO",
            flush=True,
        )

        response = await self._request(
            "GET",
            "/internal/teacherInfo.php",
        )

        try:
            data = await response.json()

            print(
                f"[PORTAL] TEACHER INFO SUCCESS: "
                f"type={type(data).__name__}",
                flush=True,
            )

            return data

        finally:
            response.release()

    async def get_attendance(
        self,
        pr_id: str,
        day: str,
        para_n: str,
    ) -> list[dict]:

        print(
            f"[PORTAL] GET ATTENDANCE: "
            f"pr_id={pr_id!r} "
            f"day={day!r} "
            f"para_n={para_n!r}",
            flush=True,
        )

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

            print(
                f"[PORTAL] ATTENDANCE RESPONSE: "
                f"type={type(data).__name__} "
                f"items={len(data) if isinstance(data, list) else 'N/A'}",
                flush=True,
            )

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

        print(
            f"[PORTAL] REGISTER ATTENDANCE: "
            f"cl_id={cl_id!r} "
            f"scl_id={scl_id!r} "
            f"pr_id={pr_id!r} "
            f"students={len(stdlist)}",
            flush=True,
        )

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
            try:
                data = await response.json()

                print(
                    f"[PORTAL] REGISTER ATTENDANCE JSON: "
                    f"type={type(data).__name__}",
                    flush=True,
                )

                return data

            except aiohttp.ContentTypeError:
                text = await response.text()

                print(
                    f"[PORTAL] REGISTER ATTENDANCE TEXT: "
                    f"{text[:1000]!r}",
                    flush=True,
                )

                return text

        finally:
            response.release()