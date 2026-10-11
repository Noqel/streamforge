# src/streamforge/hosters/_byse_impl.py
import json
import re
import time
import base64
from hashlib import sha256
from random import random, uniform
from urllib.parse import urljoin, urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from ecdsa import SigningKey, NIST256p

# --- PoW: import from the streamforge package, not the old flat layout ---
from ..pow import gr, er, wr


class ResolverError(Exception):
    pass


# ... Rest der Datei unverändert ...


# ----- Helper functions (unchanged) -----
def b64urldecode(data, binary=False):
    if isinstance(data, str):
        data = data.encode('utf-8')
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += b'=' * padding
    data = base64.urlsafe_b64decode(data)
    if not binary:
        data = data.decode('utf-8')
    return data


def b64urlencode(data, strip=False):
    if isinstance(data, str):
        data = data.encode('utf-8')
    result = base64.urlsafe_b64encode(data).decode('utf-8')
    if strip:
        result = result.rstrip('=')
    return result


def pick_source(sources):
    if not sources:
        return None
    def get_quality(item):
        label = item[0] if item[0] else ''
        nums = re.findall(r'(\d+)p?', label)
        return int(nums[0]) if nums else 0
    return sorted(sources, key=get_quality, reverse=True)[0][1]


def sort_sources_list(sources):
    return sources


def get_redirect_url(url, headers=None):
    try:
        resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        return resp.url
    except:
        return url


def append_headers(headers):
    if not headers:
        return ''
    return '|' + '&'.join([f'{k}={requests.utils.quote(str(v))}' for k, v in headers.items()])


# ----- AES-GCM wrapper -----
class AESGCM:
    def __init__(self, key):
        if len(key) not in (16, 24, 32):
            raise ValueError("Key must be 16, 24, or 32 bytes")
        self.key = key
        self.backend = default_backend()

    def decrypt(self, iv, ciphertext, tag=None, aad=b''):
        if tag is None:
            tag = b''
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), backend=self.backend)
        decryptor = cipher.decryptor()
        decryptor.authenticate_additional_data(aad)
        return decryptor.update(ciphertext) + decryptor.finalize()


def python_aesgcm(key):
    return AESGCM(key)


# ----- Main extract function -----
def extract(byse_link):
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    # ---- Extract host and media_id ----
    pattern = (
        r'(?://|\.)((?:filemoon|cinegrab|moonmov|kerapoxy|furher|1azayf9w|81u6xl9d|f16px|sb1254w9megshle|'
        r'smdfs40r|bf0skv|z1ekv717|l1afav|222i8x|8mhlloqo|96ar|xcoic|f51rm|c1z39|boosteradx|vepoin|streamlyplayero?|'
        r'(?:embedplay)?byse(?:sayeveum|tayico|zejataos|koze|sukior|jikuar|fujedu|dikamoum|buho|wihe|lapuix)?)'
        r'\.(?:sx|top?|s?k?in|link|nl|wf|com|eu|art|pro|cc|xyz|org|fun|net|lol|online))'
        r'/(?:(?:e|d|download)/)?([0-9a-zA-Z]+)'
    )
    match = re.search(pattern, byse_link)
    if not match:
        raise ResolverError('Invalid URL format')
    host = match.group(1)
    media_id = match.group(2)

    redirect_domains = ['boosteradx.online', 'byse.sx', 'streamlyplayer.online']
    if host in redirect_domains:
        host = 'streamlyplayero.online'

    web_url = f'https://{host}/e/{media_id}'
    ref = urljoin(web_url, '/')

    headers = {
        'User-Agent': UA,
        'Referer': ref,
        'Origin': ref[:-1]
    }

    # ---- Helper functions ----
    def ft(e):
        return b64urldecode(e, binary=True)

    def fh(e):
        return b64urlencode(sha256(str(e).encode('ascii')).digest(), strip=True)

    def xn(e, v):
        if v:
            v = int(v)
            e = [e[v - 1], e[len(e) - v]]
        return b''.join([ft(x) for x in e])

    def fp(x, y, z):
        from binascii import hexlify
        from os import urandom
        v_id = hexlify(urandom(x)).decode()
        d_id = hexlify(urandom(x)).decode()
        ctime = int(time.time())
        t_data = {
            'viewer_id': v_id,
            'device_id': d_id,
            'confidence': round(uniform(y, z), 2),
            'iat': ctime,
            'exp': ctime + 600
        }
        t_bdata = b64urlencode(json.dumps(t_data), strip=True)
        t_sig = b64urlencode(sha256(t_bdata.encode()).digest(), strip=True)
        token = f'{t_bdata}.{t_sig}'
        t_data.update({'token': token})
        t_data.pop('iat')
        t_data.pop('exp')
        return {'fingerprint': t_data}

    # ---- NOTE ----
    # re_func(), ye(), gr(), wr(), er() are no longer defined here.
    # They now come from the compiled Cython extension `pow_cython`.
    #   gr(bytes)                      -> list[int]  (8 x uint32)
    #   er(prefix: str, diff: int)     -> str        (nonce)
    #   wr(list[int])                  -> int        (leading-zero bits)
    # ------------------

    # ---- ADAPTIVE wn() ----
    def wn(ch):
        payload = {
            'challenge_id': ch.get('challenge_id'),
            'nonce': ch.get('nonce'),
            'viewer_id': '',
            'device_id': '',
        }

        # If signature/public_key are provided, use them
        if 'signature' in ch and 'public_key' in ch:
            payload['signature'] = ch['signature']
            payload['public_key'] = ch['public_key']
        else:
            # Generate new signature/public_key
            sk = SigningKey.generate(curve=NIST256p, hashfunc=sha256)
            vk = sk.verifying_key.to_string()
            signature = sk.sign(ch.get('nonce', '').encode(), hashfunc=sha256)
            payload['signature'] = b64urlencode(signature, strip=True)
            payload['public_key'] = {
                'crv': 'P-256',
                'ext': True,
                'key_ops': ['verify'],
                'kty': 'EC',
                'x': b64urlencode(vk[:32], strip=True),
                'y': b64urlencode(vk[32:], strip=True)
            }

        # Minimal client info (some servers require it)
        payload['client'] = {
            'user_agent': UA,
            'platform': 'Android',
            'platform_version': '10.0.0',
            'model': 'TX6s'
        }

        return payload

    # ---- Create session with retries ----
    session = requests.Session()
    session.cookies.clear()
    retry = Retry(
        total=2,
        read=2,
        connect=2,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.timeout = (15, 120)
    session.headers.update(headers)

    def http_get(url, extra_headers=None):
        if extra_headers:
            headers_copy = session.headers.copy()
            headers_copy.update(extra_headers)
            resp = session.get(url, headers=headers_copy)
        else:
            resp = session.get(url)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code} on GET {url}")
        return resp

    def http_post(url, extra_headers=None, data=None, json_data=None, timeout=None):
        if extra_headers:
            headers_copy = session.headers.copy()
            headers_copy.update(extra_headers)
        else:
            headers_copy = session.headers
        if json_data is not None:
            resp = session.post(url, headers=headers_copy, json=json_data, timeout=timeout or session.timeout)
        else:
            resp = session.post(url, headers=headers_copy, data=data, timeout=timeout or session.timeout)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code} on POST {url}")
        return resp

    # ---- Step 1: Get details ----
    embed = ''
    details_url = f'{ref}api/videos/{media_id}/details'
    try:
        resp = http_get(details_url)
        details = resp.json()
    except Exception:
        embed = 'embed/'
        details_url = f'{ref}api/videos/{media_id}/{embed}details'
        try:
            resp = http_get(details_url)
            details = resp.json()
        except Exception:
            raise ResolverError('Video Link Not Found (details failed)')

    # ---- Step 2: IGNORE embed_frame_url ----

    # ---- Step 3: Get settings ----
    settings_url = f'{ref}api/videos/{media_id}/{embed}settings'
    resp = http_get(settings_url)
    settings = resp.json()

    # ---- Step 4: Handle captcha if required ----
    if settings.get('captcha_required'):
        challenge_url = f'{ref}api/videos/access/challenge'
        resp = http_post(challenge_url, data={})
        challenge = resp.json()

        attest_url = f'{ref}api/videos/access/attest'
        time.sleep(1)
        attest_payload = wn(challenge)

        try:
            resp = http_post(attest_url, json_data=attest_payload, timeout=(15, 120))
            attest = resp.json()
        except Exception as e:
            raise ResolverError(f'Attest failed: {e}')

        fingerprint = {
            'token': attest['token'],
            'viewer_id': attest['viewer_id'],
            'device_id': attest['device_id'],
            'confidence': attest['confidence']
        }

        captcha_url = f'{ref}api/videos/{media_id}/{embed}captcha'
        resp = http_post(captcha_url, json_data={'fingerprint': fingerprint})
        captcha = resp.json()

        # ---- Cython-powered PoW solve ----
        # er() is compiled C; this is the bottleneck of the whole flow.
        solution = er(captcha['pow_nonce'], captcha['pow_difficulty'])

        if solution is None:
            raise ResolverError('Unable to solve captcha (timeout)')

        verify_url = f'{ref}api/videos/{media_id}/{embed}captcha/verify'
        post_data = {'pow_token': captcha['pow_token'], 'solution': solution, 'fingerprint': fingerprint}
        resp = http_post(verify_url, json_data=post_data)
        verify = resp.json()
        session.headers.update({'X-Captcha-Token': verify.get('token')})

        playback_url = f'{ref}api/videos/{media_id}/{embed}playback'
        resp = http_post(playback_url, json_data={'fingerprint': fingerprint})
        data = resp.json()
    else:
        playback_url = f'{ref}api/videos/{media_id}/{embed}playback'
        resp = http_post(playback_url, json_data=fp(16, 0.83, 0.94))
        data = resp.json()

    # ---- Step 5: Extract sources ----
    sources = data.get('sources')
    if sources:
        sources_list = [(x.get('label'), x.get('url')) for x in sources]
        uri = pick_source(sources_list)
        if uri.startswith('/'):
            uri = urljoin(ref, uri)
        final_url = get_redirect_url(uri, headers=session.headers)
        return final_url + append_headers(session.headers)

    # ---- Step 6: Encrypted playback ----
    pd = data.get('playback')
    if pd:
        iv = ft(pd.get('iv'))
        key = xn(pd.get('key_parts'), pd.get('version'))
        pl = ft(pd.get('payload'))
        cipher = python_aesgcm(key)
        if len(pl) > 16:
            tag = pl[-16:]
            ciphertext = pl[:-16]
            try:
                ct = cipher.decrypt(iv, ciphertext, tag)
            except:
                ct = cipher.decrypt(iv, pl)
        else:
            ct = cipher.decrypt(iv, pl)
        ct = json.loads(ct.decode('latin-1'))
        sources = ct.get('sources')
        if sources:
            sources_list = [(x.get('label'), x.get('url')) for x in sources]
            uri = pick_source(sources_list)
            session.headers.pop('X-Captcha-Token', None)
            return uri + append_headers(session.headers)

    raise ResolverError('No sources found')