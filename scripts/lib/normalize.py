"""URL and text normalization helpers."""
from __future__ import annotations

import re
from typing import Optional

_TRACKING_RE = re.compile(
    r'(?:^|&)(?:utm_source|utm_medium|utm_campaign|utm_term|utm_content|'
    r'fbclid|gclid|gclsrc|dclid|msclkid|twclid|ref|igshid|share_id|si|'
    r'mc_cid|mc_eid|oly_enc_id|vero_id|__s|ss|s_kwcid|assetType|'
    r'mkt_tok|trk|nr_email_referer|ml_sub|ml_eid|wickedid)=[^&]*',
    re.IGNORECASE,
)
_INDEX_RE = re.compile(r'/(?:index|default|home)\.html?$', re.IGNORECASE)


def normalize_url(url: Optional[str]) -> Optional[str]:
    """Strip tracking params, fragment, trailing slash, index.html."""
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if len(url) < 12 or not url.startswith(('http://', 'https://')):
        return None
    url = url.split('#', 1)[0]
    if '?' in url:
        path, query = url.split('?', 1)
        cleaned = _TRACKING_RE.sub('', query)
        cleaned = cleaned.lstrip('&')
        url = path + ('?' + cleaned if cleaned else '')
    url = _INDEX_RE.sub('', url)
    if url.count('/') > 2 and url.endswith('/'):
        url = url[:-1]
    return url if len(url) >= 12 else None


_MD_HEADER_RE = re.compile(r'^#{1,6}\s+', re.MULTILINE)
_MD_EMPHASIS_RE = re.compile(r'(\*\*|__|\*|_|`)')
_MD_LINK_RE = re.compile(r'\[([^\]]+)\]\([^)]+\)')
_URL_RE = re.compile(r'https?://\S+')
_HR_RE = re.compile(r'^[\-\*=]{3,}\s*$', re.MULTILINE)
_TABLE_PIPE_RE = re.compile(r'\s*\|\s*')

_TTS_REPLACEMENTS = {
    '—': '，',
    '–': '，',
    '·': '，',
    '…': '。',
    '“': '"',
    '”': '"',
    '‘': "'",
    '’': "'",
    '《': '',
    '》': '',
    '【': '',
    '】': '',
}


def sanitize_for_tts(markdown: str) -> str:
    """Convert Markdown body into plain text suitable for TTS."""
    if not markdown:
        return ""
    text = markdown
    text = _MD_LINK_RE.sub(r'\1', text)
    text = _URL_RE.sub('', text)
    text = _MD_HEADER_RE.sub('', text)
    text = _HR_RE.sub('', text)
    text = _MD_EMPHASIS_RE.sub('', text)
    text = _TABLE_PIPE_RE.sub('', text)
    for src, dst in _TTS_REPLACEMENTS.items():
        text = text.replace(src, dst)
    text = re.sub(r'\n{2,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()
