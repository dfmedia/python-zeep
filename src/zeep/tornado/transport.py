"""
Adds async tornado.gen support to Zeep.

"""
import logging
import urllib
import bindings

from tornado import gen, httpclient
from requests import Response, Session
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from zeep.transports import Transport
from zeep.utils import get_version
from zeep.wsdl.utils import etree_to_string

__all__ = ['TornadoAsyncTransport']


class TornadoAsyncTransport(Transport):
    """Asynchronous Transport class using tornado gen."""
    binding_classes = [
        bindings.AsyncSoap11Binding,
        bindings.AsyncSoap12Binding]

    def __init__(self, cache=None, timeout=300, operation_timeout=None,
                 session=None):
        self.cache = cache
        self.load_timeout = timeout
        self.operation_timeout = operation_timeout
        self.logger = logging.getLogger(__name__)

        self.session = session or Session()
        self.session.headers['User-Agent'] = (
            'Zeep/%s (www.python-zeep.org)' % (get_version()))

    def _load_remote_data(self, url):
        client = httpclient.HTTPClient()
        kwargs = {'method': 'GET'}
        http_req = httpclient.HTTPRequest(url, **kwargs)
        response = client.fetch(http_req)
        return response.body

    @gen.coroutine
    def post(self, address, message, headers):
        response = yield self.fetch(address, 'POST', headers, message)

        raise gen.Return(response)

    @gen.coroutine
    def post_xml(self, address, envelope, headers):
        message = etree_to_string(envelope)

        response = yield self.post(address, message, headers)

        raise gen.Return(response)

    @gen.coroutine
    def get(self, address, params, headers):
        if params:
            address += '?' + urllib.urlencode(params)
        response = yield self.fetch(address, 'GET', headers)

        raise gen.Return(response)

    @gen.coroutine
    def fetch(self, address, method, headers, message=None):
        async_client = httpclient.AsyncHTTPClient()

        # extracting auth
        auth_username = None
        auth_password = None
        auth_mode = None

        if self.session.auth:
            if type(self.session.auth) is tuple:
                auth_username = self.session.auth[0]
                auth_password = self.session.auth[1]
                auth_mode = 'basic'
            elif type(self.session.auth) is HTTPBasicAuth:
                auth_username = self.session.username
                auth_password = self.session.password
                auth_mode = 'basic'
            elif type(self.session.auth) is HTTPDigestAuth:
                auth_username = self.session.username
                auth_password = self.session.password
                auth_mode = 'digest'
            else:
                raise StandardError('Not supported authentication.')

        # extracting client cert
        client_cert = None
        client_key = None

        if self.session.cert:
            if type(self.session.cert) is str:
                client_cert = self.session.cert
            elif type(self.session.cert) is tuple:
                client_cert = self.session.cert[0]
                client_key = self.session.cert[1]

        parsed_headears = {v[0]: v[1] for k, v in self.session.headers._store.iteritems()}

        kwargs = {
            'method': method,
            'request_timeout': self.load_timeout,
            'headers': dict(headers, **parsed_headears),
            'auth_username': auth_username,
            'auth_password': auth_password,
            'auth_mode': auth_mode,
            'validate_cert': self.session.verify,
            'client_key': client_key,
            'client_cert': client_cert
        }

        if message:
            kwargs['body'] = message

        http_req = httpclient.HTTPRequest(address, **kwargs)
        response = yield async_client.fetch(http_req)

        raise gen.Return(self.new_response(response))

    def new_response(self, response):
        """Convert an tornado.HTTPResponse object to a requests.Response object"""
        new = Response()
        new._content = response.body
        new.status_code = response.code
        new.headers = response.headers # seems that headers may be in a wrong format here
        return new