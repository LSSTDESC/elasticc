import sys
import requests
import logging

_logger = logging.getLogger(__name__)
if not _logger.hasHandlers():
    _logout = logging.StreamHandler( sys.stderr )
    _logger.addHandler( _logout )
    _formatter = logging.Formatter( f'[%(asctime)s - %(levelname)s] - %(message)s',
                                    datefmt='%Y-%m-%d %H:%M:%S' )
    _logout.setFormatter( _formatter )
    _logger.setLevel( logging.INFO )

class TomConnection:
    def __init__( self, urlbase, username, password, logger=_logger ):
        self.logger = logger
        self.urlbase = urlbase
        self.rqs = requests.session()
        res = self.rqs.get( f'{urlbase}/accounts/login/' )
        res = self.rqs.post( f'{urlbase}/accounts/login/',
                             data={ "username": username,
                                    "password": password,
                                    "csrfmiddlewaretoken": self.rqs.cookies['csrftoken'] } )
        if res.status_code != 200:
            self.logger.error( "Failed to log in" )
            raise RuntimeError( "Login failure" )
        if 'Please enter a correct' in res.text:
            # I really hate this.  I'm doing this based on what I saw,
            # and I don't feel confident that exactly this text will show up
            # when the login fails.  But, I haven't found clean
            # documentation on how to log into a django site from an app
            # like this using the standard authentication stuff.
            self.logger.error( "Failed to log in.  I think.  Put in a debug break and look at res.text." )
            raise RuntimeError( "Login failure" )
        self.rqs.headers.update( { 'X-CSRFToken': self.rqs.cookies['csrftoken'] } )
