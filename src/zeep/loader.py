import os.path
import typing
import re
import io
from urllib.parse import urljoin, urlparse, urlunparse

from lxml import etree
from lxml.etree import Resolver, XMLParser, XMLSyntaxError, fromstring, parse, tostring

from zeep.exceptions import DTDForbidden, EntitiesForbidden, XMLSyntaxError
from zeep.settings import Settings


class ImportResolver(Resolver):
    """Custom lxml resolve to use the transport object"""

    def __init__(self, transport):
        self.transport = transport

    def resolve(self, url, pubid, context):
        if urlparse(url).scheme in ("http", "https"):
            content = self.transport.load(url)
            return self.resolve_string(content, context)


def parse_xml(content: bytes, transport, base_url=None, settings=None):
    """Parse an XML string and return the root Element.

    :param content: The XML string
    :type content: str
    :param transport: The transport instance to load imported documents
    :type transport: zeep.transports.Transport
    :param base_url: The base url of the document, used to make relative
      lookups absolute.
    :type base_url: str
    :param settings: A zeep.settings.Settings object containing parse settings.
    :type settings: zeep.settings.Settings
    :returns: The document root
    :rtype: lxml.etree._Element

    """

    # content = content.decode('utf-8', 'replace')
    print(f'CONTENT TYPE 1: {type(content)}')
    content = re.sub(b'\\xa9|\\xc2|\\xa0|\\xe2|\\x80|\\x8b|\\x00', b'', content)
    content = content.decode('ascii', 'ignore')
    print(f'CONTENT TYPE 1.5: {type(content)}')

    content= content.encode('utf-8')
    print(f'CONTENT TYPE 2: {type(content)}')

    settings = settings or Settings()
    recover = not settings.strict
    parser = XMLParser(
        remove_comments=True,
        resolve_entities=False,
        recover=recover,
        huge_tree=settings.xml_huge_tree,
        ns_clean=True
    )
    parser.resolvers.add(ImportResolver(transport))
    print(f'PARSER: {parser}')
    try:
        elementtree = fromstring(content, parser=parser, base_url=base_url)
        docinfo = elementtree.getroottree().docinfo
        print(f'DOCINFO: {docinfo}')

        # print(f'START PARSE')
        # parse_tree = etree.parse(content, parser)
        # print(f'PARSE TREE')
        # elementtree = etree.tostring(parse_tree.getroot())
        # print(f'ELEMENT TREE')
        # docinfo = elementtree.getroottree().docinfo

        if docinfo.doctype:
            print(f'IF DOCINFO')
            if settings.forbid_dtd:
                raise DTDForbidden(
                    docinfo.doctype, docinfo.system_url, docinfo.public_id
                )
        if settings.forbid_entities:
            print(f'IF FORBID')
            for dtd in docinfo.internalDTD, docinfo.externalDTD:
                if dtd is None:
                    continue
                for entity in dtd.iterentities():
                    raise EntitiesForbidden(entity.name, entity.content)
        print('RETURN ETREE')
        return elementtree
    except etree.XMLSyntaxError as exc:
        raise XMLSyntaxError(
            "Invalid XML content received !! (%s)" % exc.msg, content=content
        )
    except Exception as exc:
        print(f'EXCEPTION')
        print(exc.args)





def load_external(url: typing.IO, transport, base_url=None, settings=None):
    """Load an external XML document.

    :param url:
    :param transport:
    :param base_url:
    :param settings: A zeep.settings.Settings object containing parse settings.
    :type settings: zeep.settings.Settings

    """
    settings = settings or Settings()
    if hasattr(url, "read"):
        content = url.read()
    else:
        if base_url:
            url = absolute_location(url, base_url)
        content = transport.load(url)
    print('load external')
    return parse_xml(content, transport, base_url, settings=settings)


async def load_external_async(url: typing.IO, transport, base_url=None, settings=None):
    """Load an external XML document.

    :param url:
    :param transport:
    :param base_url:
    :param settings: A zeep.settings.Settings object containing parse settings.
    :type settings: zeep.settings.Settings

    """
    settings = settings or Settings()
    if hasattr(url, "read"):
        content = url.read()
    else:
        if base_url:
            url = absolute_location(url, base_url)
        content = await transport.load(url)
    print('load external async')
    return parse_xml(content, transport, base_url, settings=settings)


def normalize_location(settings, url, base_url):
    """Return a 'normalized' url for the given url.

    This will make the url absolute and force it to https when that setting is
    enabled.

    """
    if base_url:
        url = absolute_location(url, base_url)

    if base_url and settings.force_https:
        base_url_parts = urlparse(base_url)
        url_parts = urlparse(url)
        if (
            base_url_parts.netloc == url_parts.netloc
            and base_url_parts.scheme != url_parts.scheme
        ):
            url = urlunparse(("https",) + url_parts[1:])
    return url


def absolute_location(location, base):
    """Make an url absolute (if it is optional) via the passed base url.

    :param location: The (relative) url
    :type location: str
    :param base: The base location
    :type base: str
    :returns: An absolute URL
    :rtype: str

    """
    if location == base:
        return location

    if urlparse(location).scheme in ("http", "https", "file"):
        return location

    if base and urlparse(base).scheme in ("http", "https", "file"):
        return urljoin(base, location)
    else:
        if os.path.isabs(location):
            return location
        if base:
            return os.path.realpath(os.path.join(os.path.dirname(base), location))
    return location


def is_relative_path(value):
    """Check if the given value is a relative path

    :param value: The value
    :type value: str
    :returns: Boolean indicating if the url is relative. If it is absolute then
      False is returned.
    :rtype: boolean

    """
    if urlparse(value).scheme in ("http", "https", "file"):
        return False
    return not os.path.isabs(value)
