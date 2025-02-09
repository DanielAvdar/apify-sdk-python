from __future__ import annotations

import codecs
import pickle

try:
    from scrapy import Request, Spider
    from scrapy.http.headers import Headers
    from scrapy.utils.request import request_from_dict
except ImportError as exc:
    raise ImportError(
        'To use this module, you need to install the "scrapy" extra. Run "pip install apify[scrapy]".',
    ) from exc

from apify._crypto import crypto_random_object_id
from apify.actor import Actor


def to_apify_request(scrapy_request: Request, spider: Spider) -> dict:
    """Convert a Scrapy request to an Apify request.

    Args:
        scrapy_request: The Scrapy request to be converted.
        spider: The Scrapy spider that the request is associated with.

    Raises:
        TypeError: If the scrapy_request is not an instance of the scrapy.Request class.

    Returns:
        The converted Apify request.
    """
    if not isinstance(scrapy_request, Request):
        raise TypeError('scrapy_request must be an instance of the scrapy.Request class')

    call_id = crypto_random_object_id(8)
    Actor.log.debug(f'[{call_id}]: to_apify_request was called (scrapy_request={scrapy_request})...')

    apify_request = {
        'url': scrapy_request.url,
        'method': scrapy_request.method,
        'userData': scrapy_request.meta.get('userData', {}),
    }

    if isinstance(scrapy_request.headers, Headers):
        apify_request['headers'] = dict(scrapy_request.headers.to_unicode_dict())
    else:
        Actor.log.warning(
            f'scrapy_request.headers is not an instance of the scrapy.http.headers.Headers class, scrapy_request.headers = {scrapy_request.headers}',
        )

    # Add 'id' to the apify_request
    if scrapy_request.meta.get('apify_request_id'):
        apify_request['id'] = scrapy_request.meta['apify_request_id']

    # Add 'uniqueKey' to the apify_request
    if scrapy_request.meta.get('apify_request_unique_key'):
        apify_request['uniqueKey'] = scrapy_request.meta['apify_request_unique_key']

    # Serialize the Scrapy Request and store it in the apify_request.
    #   - This process involves converting the Scrapy Request object into a dictionary, encoding it to base64,
    #     and storing it as 'scrapy_request' within the 'userData' dictionary of the apify_request.
    #   - The serialization process can be referenced at: https://stackoverflow.com/questions/30469575/.
    scrapy_request_dict = scrapy_request.to_dict(spider=spider)
    scrapy_request_dict_encoded = codecs.encode(pickle.dumps(scrapy_request_dict), 'base64').decode()

    apify_request['userData']['scrapy_request'] = scrapy_request_dict_encoded

    Actor.log.debug(f'[{call_id}]: scrapy_request was converted to the apify_request={apify_request}')
    return apify_request


def to_scrapy_request(apify_request: dict, spider: Spider) -> Request:
    """Convert an Apify request to a Scrapy request.

    Args:
        apify_request: The Apify request to be converted.
        spider: The Scrapy spider that the request is associated with.

    Raises:
        TypeError: If the apify_request is not a dictionary.
        ValueError: If the apify_request does not contain the required keys.

    Returns:
        The converted Scrapy request.
    """
    if not isinstance(apify_request, dict):
        raise TypeError('apify_request must be a dictionary')

    required_keys = ['url', 'method', 'id', 'uniqueKey']
    missing_keys = [key for key in required_keys if key not in apify_request]

    if missing_keys:
        raise ValueError(f'apify_request must contain {", ".join(map(repr, missing_keys))} key(s)')

    call_id = crypto_random_object_id(8)
    Actor.log.debug(f'[{call_id}]: to_scrapy_request was called (apify_request={apify_request})...')

    # If the apify_request comes from the Scrapy
    if 'userData' in apify_request and 'scrapy_request' in apify_request['userData']:
        # Deserialize the Scrapy Request from the apify_request.
        #   - This process involves decoding the base64-encoded request data and reconstructing
        #     the Scrapy Request object from its dictionary representation.
        Actor.log.debug(f'[{call_id}]: Restoring the Scrapy Request from the apify_request...')

        scrapy_request_dict_encoded = apify_request['userData']['scrapy_request']
        if not isinstance(scrapy_request_dict_encoded, str):
            raise TypeError('scrapy_request_dict_encoded must be a string')

        scrapy_request_dict = pickle.loads(codecs.decode(scrapy_request_dict_encoded.encode(), 'base64'))
        if not isinstance(scrapy_request_dict, dict):
            raise TypeError('scrapy_request_dict must be a dictionary')

        scrapy_request = request_from_dict(scrapy_request_dict, spider=spider)
        if not isinstance(scrapy_request, Request):
            raise TypeError('scrapy_request must be an instance of the Request class')

        Actor.log.debug(f'[{call_id}]: Scrapy Request successfully reconstructed (scrapy_request={scrapy_request})...')

        # Update the meta field with the meta field from the apify_request
        meta = scrapy_request.meta or {}
        meta.update({'apify_request_id': apify_request['id'], 'apify_request_unique_key': apify_request['uniqueKey']})
        scrapy_request._meta = meta  # scrapy_request.meta is a property, so we have to set it like this

    # If the apify_request comes directly from the Request Queue, typically start URLs
    else:
        Actor.log.debug(f'[{call_id}]: gonna create a new Scrapy Request (cannot be restored)')

        scrapy_request = Request(
            url=apify_request['url'],
            method=apify_request['method'],
            meta={
                'apify_request_id': apify_request['id'],
                'apify_request_unique_key': apify_request['uniqueKey'],
            },
        )

    # Add optional 'headers' field
    if 'headers' in apify_request:
        if isinstance(apify_request['headers'], dict):
            scrapy_request.headers = Headers(apify_request['headers'])
        else:
            Actor.log.warning(
                f'apify_request[headers] is not an instance of the dict class, apify_request[headers] = {apify_request["headers"]}',
            )

    # Add optional 'userData' field
    if 'userData' in apify_request:
        scrapy_request.meta['userData'] = apify_request['userData']

    Actor.log.debug(f'[{call_id}]: an apify_request was converted to the scrapy_request={scrapy_request}')
    return scrapy_request
