"""Offline quote routing: compare licensed, verified information offers."""
from decimal import Decimal, InvalidOperation

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
