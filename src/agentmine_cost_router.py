"""Offline quote routing: compare licensed, verified information offers."""
from decimal import Decimal, InvalidOperation
from ipaddress import ip_address
from socket import inet_aton
from urllib.parse import urlsplit


def _public_source_url(value):
    """Require an attributable HTTPS source without embedded credentials."""
    if not isinstance(value, str) or not value or len(value) > 2048:
        return False
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != 'https' or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.port not in (None, 443)
                or parsed.query or parsed.fragment):
            return False
        # urlsplit leaves percent-encoded hostnames undecoded, while HTTP
        # clients may decode them to private IPs (e.g. 127.0.0.%31).
        # It also strips embedded tabs/newlines when parsing a URL. Reject
        # ambiguous authority encodings and raw controls before attribution.
        if ('%' in parsed.netloc or '\\' in parsed.netloc
                or any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127
                       for ch in value)):
            return False
        host = parsed.hostname.rstrip('.').lower()
        # A provenance URL must be publicly addressable. Internal hosts and
        # private/loopback/reserved IPs are not evidence of a public offer.
        try:
            return ip_address(host).is_global
        except ValueError:
            # inet_aton is a local parser (no DNS/network). It catches legacy
            # numeric IPv4 spellings such as 127.1, 0177.0.0.1 and
            # 0x7f.0.0.1 that ip_address rejects but URL clients may resolve
            # to loopback or private addresses.
            try:
                return ip_address(inet_aton(host)).is_global
            except OSError:
                # DNS hostnames must be multi-label and not explicitly local.
                return ('.' in host and not host.endswith(
                    ('.localhost', '.localdomain', '.local', '.internal', '.home.arpa', '.lan')))
    except ValueError:
        return False

def _budget(value):
    """A missing, nonfinite or negative budget must never permit a route."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError('max_total_usd must be a finite nonnegative amount')
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError('max_total_usd must be a finite nonnegative amount') from None
    if not amount.is_finite() or amount < 0:
        raise ValueError('max_total_usd must be a finite nonnegative amount')
    return amount

def choose(quotes, *, max_age_seconds, min_quality, max_total_usd):
    # Validate caller policy even when no quotes are supplied. Invalid policy
    # values must not silently widen the age, quality or spending gates.
    if type(max_age_seconds) not in (int, float) or not 0 <= max_age_seconds < float('inf'):
        raise ValueError('max_age_seconds must be finite and nonnegative')
    if type(min_quality) not in (int, float) or not 0 <= min_quality <= 1:
        raise ValueError('min_quality must be finite and between zero and one')
    budget = _budget(max_total_usd)
    eligible=[]
    for q in quotes:
        if not isinstance(q, dict):
            continue
        try:
            if not isinstance(q.get('provider'),str) or not q['provider'].strip(): continue
            if q.get('license_allowed') is not True or q.get('verified') is not True: continue
            # A quote with no safe source cannot be traced or independently audited.
            # Caller-provided license/verification flags are still not proof.
            if not _public_source_url(q.get('source_url')): continue
            age=q['age_seconds']; quality=q['quality']
            if isinstance(age,bool) or isinstance(quality,bool) or not isinstance(age,(int,float)) or not isinstance(quality,(int,float)): continue
            if not (0<=age<float('inf') and age<=max_age_seconds and 0<=quality<=1 and quality>=min_quality): continue
            parts=[Decimal(str(q[k])) for k in ('source_usd','tokens_usd','network_usd')]
            if any(not p.is_finite() or p<0 for p in parts): continue
            cost=sum(parts)
            if not cost.is_finite() or cost<0 or cost>budget: continue
            eligible.append((cost,-quality,q['provider'],q))
        except (KeyError,TypeError,ValueError,InvalidOperation): continue
    if not eligible: return {'status':'no_eligible_quote','selected':None}
    cost,_,_,q=min(eligible,key=lambda x:x[:3])
    return {'status':'selected','selected':q['provider'],'total_usd':str(cost),'source':q.get('source_url')}
