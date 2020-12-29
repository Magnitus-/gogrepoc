import getpass
import html5lib

from .base import BaseClass

try:
    # python 2
    from urlparse import urlparse, unquote
except ImportError:
    # python 3
    from urllib.parse import urlparse, unquote

# python 2 / 3 renames
try: input = raw_input
except NameError: pass

class Login(BaseClass):
    def __init__(self, cookie, logger, user_agent):
        self.cookie = cookie
        self.logger = logger
        self.user_agent = user_agent
    
    def __call__(self, user, passwd):
        """Attempts to log into GOG and saves the resulting cookiejar to disk.
        """
        login_data = {'user': user,
                    'passwd': passwd,
                    'auth_url': None,
                    'login_token': None,
                    'two_step_url': None,
                    'two_step_token': None,
                    'two_step_security_code': None,
                    'login_success': False,
                    }

        self.cookie.clear()  # reset cookiejar

        # prompt for login/password if needed
        if login_data['user'] is None:
            login_data['user'] = input("Username: ")
        if login_data['passwd'] is None:
            login_data['passwd'] = getpass.getpass()

        self.logger.info("attempting gog login as '{}' ...".format(login_data['user']))
        
        loginSession = self.makeGOGSession(True)

        # fetch the auth url
        
        page_response = self.request(loginSession, self.GOG_HOME_URL)    
        etree = html5lib.parse(page_response.text, namespaceHTMLElements=False)
        for elm in etree.findall('.//script'):
            if elm.text is not None and 'GalaxyAccounts' in elm.text:
                authCandidates = elm.text.split("'")
                for authCandidate in authCandidates:
                    if 'auth' in authCandidate:
                        testAuth = urlparse(authCandidate)
                        if testAuth.scheme == "https":
                            login_data['auth_url'] = authCandidate
                            break
                if login_data['auth_url']:
                    break
                    
        if not login_data['auth_url']:
            self.logger.error("cannot find auth url, please report to the maintainer")
            exit(1)

        page_response = self.request(loginSession,login_data['auth_url'])          
        # fetch the login token
        etree = html5lib.parse(page_response.text, namespaceHTMLElements=False)
        # Bail if we find a request for a reCAPTCHA
        if len(etree.findall('.//div[@class="g-recaptcha form__recaptcha"]')) > 0:
            self.logger.error("cannot continue, gog is asking for a reCAPTCHA :(  try again in a few minutes.")
            return
        for elm in etree.findall('.//input'):
            if elm.attrib['id'] == 'login__token':
                login_data['login_token'] = elm.attrib['value']
                break

        # perform login and capture two-step token if required
        page_response = self.request(
            loginSession,
            self.GOG_LOGIN_URL, 
            data={
                'login[username]': login_data['user'],
                'login[password]': login_data['passwd'],
                'login[login]': '',
                'login[_token]': login_data['login_token']
            }
        ) 
        etree = html5lib.parse(page_response.text, namespaceHTMLElements=False)
        if 'two_step' in page_response.url:
            login_data['two_step_url'] = page_response.url
            for elm in etree.findall('.//input'):
                if elm.attrib['id'] == 'second_step_authentication__token':
                    login_data['two_step_token'] = elm.attrib['value']
                    break
        elif 'on_login_success' in page_response.url:
            login_data['login_success'] = True

        # perform two-step if needed
        if login_data['two_step_url'] is not None:
            login_data['two_step_security_code'] = input("enter two-step security code: ")

            # Send the security code back to GOG
            page_response = self.request(
                loginSession,
                login_data['two_step_url'], 
                data={
                    'second_step_authentication[token][letter_1]': login_data['two_step_security_code'][0],
                    'second_step_authentication[token][letter_2]': login_data['two_step_security_code'][1],
                    'second_step_authentication[token][letter_3]': login_data['two_step_security_code'][2],
                    'second_step_authentication[token][letter_4]': login_data['two_step_security_code'][3],
                    'second_step_authentication[send]': "",
                    'second_step_authentication[_token]': login_data['two_step_token']
                }
            )
            if 'on_login_success' in page_response.url:
                login_data['login_success'] = True

        # save cookies on success
        if login_data['login_success']:
            self.logger.info('login successful!')
            for c in loginSession.cookies:
                self.cookie.set_cookie(c)
            self.cookie.save()
        else:
            self.logger.error('login failed, verify your username/password and try again.')