import re
import json
import base64
from urllib.parse import urljoin
import requests


class ResolverError(Exception):
    pass

# ----- Utility functions (replacing helpers) -----

def b64decode(data):
    """Decode base64 (standard, not URL‑safe)."""
    # Add padding if needed
    if isinstance(data, str):
        data = data.encode('utf-8')
    missing = len(data) % 4
    if missing:
        data += b'=' * (4 - missing)
    return base64.b64decode(data).decode('utf-8', errors='ignore')

def pick_source(sources):
    """
    Return the m3u8 URL, checking the label first, then the URL itself."""
    for label, url in sources:
        if (label or "").lower() in ("m3u8", "hls", "master"):
            return url
    for label, url in sources:
        if ".m3u8" in (url or "").lower():
            return url

def append_headers(headers):
    """Convert headers dict to a query string appended to the URL."""
    if not headers:
        return ''
    return '|' + '&'.join([f'{k}={requests.utils.quote(str(v))}' for k, v in headers.items()])

def scrape_sources(html, patterns=None):
    """
    Extract video URLs from HTML using regex patterns.
    Returns a list of (label, url) tuples.
    """
    if patterns is None:
        patterns = []
    sources = []
    for pattern in patterns:
        for match in re.finditer(pattern, html, re.DOTALL | re.IGNORECASE):
            url = match.group('url')
            label = match.group('label') if 'label' in match.groupdict() else 'unknown'
            sources.append((label, url))
    # Generic patterns for m3u8 and mp4
    generic_patterns = [
        r'(?P<url>https?://[^\s"\']+\.m3u8[^\s"\']*)',
        r'(?P<url>https?://[^\s"\']+\.mp4[^\s"\']*)',
    ]
    for pattern in generic_patterns:
        for match in re.finditer(pattern, html, re.IGNORECASE):
            url = match.group('url')
            # Try to get resolution from URL or context; default to 0
            sources.append(('generic', url))
    return sources

# ----- VoeResolver class -----

class VoeResolver:
    name = 'Voe'
    domains = [
        'voe.sx', 'voe-unblock.com', 'voe-unblock.net', 'voeunblock.com', 'un-block-voe.net',
        'voeunbl0ck.com', 'voeunblck.com', 'voeunblk.com', 'voe-un-block.com', 'jonathansociallike.com'
        'voeun-block.net', 'v-o-e-unblock.com', 'edwardarriveoften.com', 'nathanfromsubject.com',
        'audaciousdefaulthouse.com', 'launchreliantcleaverriver.com', 'kennethofficialitem.com',
        'reputationsheriffkennethsand.com', 'fittingcentermondaysunday.com', 'lukecomparetwo.com',
        'housecardsummerbutton.com', 'fraudclatterflyingcar.com', 'wolfdyslectic.com',
        'bigclatterhomesguideservice.com', 'uptodatefinishconferenceroom.com', 'jayservicestuff.com',
        'realfinanceblogcenter.com', 'tinycat-voe-fashion.com', '35volitantplimsoles5.com',
        '20demidistance9elongations.com', 'telyn610zoanthropy.com', 'toxitabellaeatrebates306.com',
        'greaseball6eventual20.com', '745mingiestblissfully.com', '19turanosephantasia.com',
        '30sensualizeexpression.com', '321naturelikefurfuroid.com', '449unceremoniousnasoseptal.com',
        'guidon40hyporadius9.com', 'cyamidpulverulence530.com', 'boonlessbestselling244.com',
        'antecoxalbobbing1010.com', 'matriculant401merited.com', 'scatch176duplicities.com',
        'availedsmallest.com', 'counterclockwisejacky.com', 'simpulumlamerop.com', 'paulkitchendark.com',
        'metagnathtuggers.com', 'gamoneinterrupted.com', 'chromotypic.com', 'crownmakermacaronicism.com',
        'generatesnitrosate.com', 'yodelswartlike.com', 'figeterpiazine.com', 'strawberriesporail.com',
        'valeronevijao.com', 'timberwoodanotia.com', 'apinchcaseation.com', 'nectareousoverelate.com',
        'nonesnanking.com', 'kathleenmemberhistory.com', 'stevenimaginelittle.com', 'jamiesamewalk.com',
        'bradleyviewdoctor.com', 'sandrataxeight.com', 'graceaddresscommunity.com', 'shannonpersonalcost.com',
        'cindyeyefinal.com', 'michaelapplysome.com', 'sethniceletter.com', 'brucevotewithin.com',
        'rebeccaneverbase.com', 'loriwithinfamily.com', 'roberteachfinal.com', 'erikcoldperson.com',
        'jasminetesttry.com', 'heatherdiscussionwhen.com', 'robertplacespace.com', 'alleneconomicmatter.com',
        'josephseveralconcern.com', 'donaldlineelse.com', 'lisatrialidea.com', 'toddpartneranimal.com',
        'jamessoundcost.com', 'brittneystandardwestern.com', 'sandratableother.com', 'robertordercharacter.com',
        'maxfinishseveral.com', 'chuckle-tube.com', 'kristiesoundsimply.com', 'adrianmissionminute.com',
        'richardsignfish.com', 'jennifercertaindevelopment.com', 'diananatureforeign.com', 'goofy-banana.com',
        'mariatheserepublican.com', 'johnalwayssame.com', 'kellywhatcould.com', 'jilliandescribecompany.com',
        'lukesitturn.com', 'mikaylaarealike.com', 'christopheruntilpoint.com', 'walterprettytheir.com',
        'crystaltreatmenteast.com', 'lauradaydo.com', 'smoki.cc', 'lancewhosedifficult.com',
        'ogladaj.me', 'dianaavoidthey.com', 'jefferycontrolmodel.com', 'marissasharecareer.com',
        'charlestoughrace.com', 'ianrequireadult.com', 'timmaybealready.com', 'jessicayeahcatch.com'
    ]
    domains += ['voeunblock{}.com'.format(x) for x in range(1, 11)]
    pattern = (
        r'(?://|\.)((?:audaciousdefaulthouse|launchreliantcleaverriver|kennethofficialitem|'
        r'reputationsheriffkennethsand|fittingcentermondaysunday|paulkitchendark|'
        r'housecardsummerbutton|fraudclatterflyingcar|35volitantplimsoles5.com|sethniceletter|'
        r'bigclatterhomesguideservice|uptodatefinishconferenceroom|edwardarriveoften|'
        r'realfinanceblogcenter|tinycat-voe-fashion|20demidistance9elongations|michaelapplysome|'
        r'telyn610zoanthropy|toxitabellaeatrebates306|greaseball6eventual20|jayservicestuff|'
        r'745mingiestblissfully|19turanosephantasia|30sensualizeexpression|sandrataxeight|'
        r'321naturelikefurfuroid|449unceremoniousnasoseptal|guidon40hyporadius9|brucevotewithin|'
        r'cyamidpulverulence530|boonlessbestselling244|antecoxalbobbing1010|lukecomparetwo|'
        r'matriculant401merited|scatch176duplicities|availedsmallest|stevenimaginelittle|'
        r'counterclockwisejacky|simpulumlamerop|wolfdyslectic|nectareousoverelate|kellywhatcould|'
        r'metagnathtuggers|gamoneinterrupted|chromotypic|crownmakermacaronicism|diananatureforeign|'
        r'yodelswartlike|figeterpiazine|strawberriesporail|valeronevijao|timberwoodanotia|'
        r'generatesnitrosate|apinchcaseation|nonesnanking|kathleenmemberhistory|goofy-banana|'
        r'jamiesamewalk|bradleyviewdoctor|graceaddresscommunity|shannonpersonalcost|cindyeyefinal|'
        r'rebeccaneverbase|loriwithinfamily|roberteachfinal|erikcoldperson|jasminetesttry|'
        r'heatherdiscussionwhen|robertplacespace|alleneconomicmatter|josephseveralconcern|'
        r'donaldlineelse|lisatrialidea|toddpartneranimal|jamessoundcost|brittneystandardwestern|'
        r'sandratableother|robertordercharacter|maxfinishseveral|chuckle-tube|kristiesoundsimply|'
        r'adrianmissionminute|nathanfromsubject|richardsignfish|jennifercertaindevelopment|'
        r'jonathansociallike|mariatheserepublican|johnalwayssame|jilliandescribecompany|'
        r'lukesitturn|mikaylaarealike|christopheruntilpoint|walterprettytheir|crystaltreatmenteast|'
        r'lauradaydo|smoki|lancewhosedifficult|ogladaj|dianaavoidthey|jefferycontrolmodel|marissasharecareer|'
        r'charlestoughrace|ianrequireadult|timmaybealready|jessicayeahcatch|'
        r'(?:v-?o-?e)?(?:-?un-?bl[o0]?c?k\d{0,2})?(?:-?voe)?)\.(?:sx|com|net|cc|me))/'
        r'(?:e/)?([0-9A-Za-z]+)'
    )

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

    def get_media_url(self, host, media_id):
        web_url = self.get_url(host, media_id)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        html = self.http_get(web_url, headers=headers).text
        # Follow redirects (like 'const currentUrl' in html)
        while 'const currentUrl' in html:
            r = re.search(r'''window\.location\.href\s*=\s*'([^']+)''', html)
            if r:
                web_url = r.group(1)
                html = self.http_get(web_url, headers=headers).text
            else:
                break

        r = re.search(r'json">\["([^"]+)"]</script>\s*<script\s*src="([^"]+)', html)
        if r:
            script_url = urljoin(web_url, r.group(2))
            script_content = self.http_get(script_url, headers=headers).text
            repl = re.search(r"(\[(?:'\W{2}'[,\]]){1,9})", script_content)
            if repl:
                s = self.voe_decode(r.group(1), repl.group(1))
                sources = [(s.get(x).split("?")[0].split(".")[-1], s.get(x)) for x in ['file', 'source', 'direct_access_url'] if x in s]
                if len(sources) > 1:
                    sources.sort(key=lambda x: int(re.sub(r"\D", "", x[0])) if re.sub(r"\D", "", x[0]) else 0)
                stream_url = pick_source(sources) + append_headers(headers)
                return stream_url

        # Fallback to scraping sources
        sources = scrape_sources(
            html,
            patterns=[
                r'''mp4["']:\s*["'](?P<url>[^"']+)["'],\s*["']video_height["']:\s*(?P<label>[^,]+)''',
                r'''hls':\s*'(?P<url>[^']+)''',
                r'''hls":\s*"(?P<url>[^"]+)",\s*"video_height":\s*(?P<label>[^,]+)'''
            ]
        )
        if sources:
            stream_url = pick_source(sources) + append_headers(headers)
            return stream_url

        raise ResolverError('No video found')

    def get_url(self, host, media_id):
        return 'https://{host}/e/{media_id}'.format(host=host, media_id=media_id)

    def http_get(self, url, headers=None):
        response = self.session.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            raise ResolverError('HTTP {} error'.format(response.status_code))
        return response

    @staticmethod
    def voe_decode(ct, luts):
        # Build lut list
        lut = [''.join([('\\' + x) if x in '.*+?^${}()|[]\\' else x for x in i]) for i in luts[2:-2].split("','")]
        txt = ''
        for i in ct:
            x = ord(i)
            if 64 < x < 91:
                x = (x - 52) % 26 + 65
            elif 96 < x < 123:
                x = (x - 84) % 26 + 97
            txt += chr(x)
        for i in lut:
            txt = re.sub(i, '', txt)
        ct = b64decode(txt)
        txt = ''.join([chr(ord(i) - 3) for i in ct])
        txt = b64decode(txt[::-1])
        return json.loads(txt)

# ----- Public API -----

def extract_voe(voe_url):
    """
    Extract the direct HLS/m3u8 URL from a VOE video link.
    """
    match = re.search(VoeResolver.pattern, voe_url)
    if not match:
        raise ResolverError('Invalid VOE URL')
    host = match.group(1)
    media_id = match.group(2)

    resolver = VoeResolver()
    return resolver.get_media_url(host, media_id)