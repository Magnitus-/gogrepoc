import codecs
import OpenSSL
import requests
import time

try:
    # python 2
    import cookielib as cookiejar
except ImportError:
    # python 3
    import http.cookiejar as cookiejar

NETSCAPE_COOKIES_FILENAME = r'cookies.txt'
NETSCAPE_COOKIES_TMP_FILENAME = r'cookies.txt.tmp'
HTTP_RETRY_COUNT = 3
HTTP_PERM_ERRORCODES = (404, 403, 503)

class BaseClass:
    GOG_HOME_URL = r'https://www.gog.com'
    GOG_ACCOUNT_URL = r'https://www.gog.com/account'
    GOG_LOGIN_URL = r'https://login.gog.com/login_check'
    HTTP_RETRY_COUNT = HTTP_RETRY_COUNT
    HTTP_TIMEOUT = 30
    HTTP_RETRY_DELAY = 5

    def makeGOGSession(self, loginSession=False):
        gogSession = requests.Session()
        gogSession.headers={'User-Agent': self.user_agent}
        if not loginSession:
            self.load_cookies()
            gogSession.cookies.update(self.cookie)
        return gogSession

    def load_cookies(self):
        # try to load as default lwp format
        try:
            self.cookie.load()
            return
        except IOError:
            pass

        # try to import as mozilla 'cookies.txt' format
        try:
            with codecs.open(NETSCAPE_COOKIES_FILENAME,"rU",'utf-8') as f1:
                with codecs.open(NETSCAPE_COOKIES_TMP_FILENAME,"w",'utf-8') as f2:
                    for line in f1:
                        line = line.replace(u"#HttpOnly_",u"")
                        line=line.strip()
                        if not (line.startswith(u"#")):
                            if (u"gog.com" in line): 
                                f2.write(line+u"\n")
            tmp_jar = cookiejar.MozillaCookieJar(NETSCAPE_COOKIES_TMP_FILENAME)
            tmp_jar.load()
            for c in tmp_jar:
                self.cookie.set_cookie(c)
            self.cookie.save()
            return
        except IOError:
            pass

        self.logger.error('failed to load cookies, did you login first?')
        raise SystemExit(1)

    #temporary request wrapper while testing sessions module in context of update. Will replace request when complete
    def request(
        self,
        session,
        url,
        args=None,
        byte_range=None,
        retries=HTTP_RETRY_COUNT,
        delay=None,
        stream=False,
        data=None
    ):
        """Performs web request to url with optional retries, delay, and byte range.
        """
        _retry = False
        if delay is not None:
            time.sleep(delay)

        try:
            if data is not None:        
                if byte_range is not None:  
                    response = session.post(
                        url, 
                        params=args, 
                        headers= {'Range':'bytes=%d-%d' % byte_range},
                        timeout=HTTP_TIMEOUT,
                        stream=stream,
                        data=data
                    )
                else:
                    response = session.post(
                        url, 
                        params=args,
                        stream=stream,
                        timeout=self.HTTP_TIMEOUT,
                        data=data
                    )
            else:
                if byte_range is not None:  
                    response = session.get(
                        url,
                        params=args,
                        headers= {'Range':'bytes=%d-%d' % byte_range},
                        timeout=self.HTTP_TIMEOUT,
                        stream=stream
                    )
                else:
                    response = session.get(
                        url, 
                        params=args,
                        stream=stream,
                        timeout=self.HTTP_TIMEOUT
                    )        
            response.raise_for_status()    
        except (requests.HTTPError, requests.URLRequired, requests.Timeout, requests.ConnectionError, OpenSSL.SSL.Error) as e:
            if isinstance(e, requests.HTTPError):
                if e.response.status_code in HTTP_PERM_ERRORCODES:  # do not retry these HTTP codes
                    warn('request failed: %s.  will not retry.', e)
                    raise
            if retries > 0:
                _retry = True
            else:
                raise

            if _retry:
                warn('request failed: %s (%d retries left) -- will retry in %ds...' % (e, retries, self.HTTP_RETRY_DELAY))
                return request(
                    session=session,
                    url=url,
                    args=args,
                    byte_range=byte_range,
                    retries=retries-1,
                    delay=self.HTTP_RETRY_DELAY
                )
        return response