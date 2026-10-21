"""Offline quote routing: compare licensed, verified information offers."""
from decimal import Decimal, InvalidOperation

def choose(quotes, *, max_age_seconds, min_quality, max_total_usd):
    eligible=[]
    for q in quotes:
        try:
            if not isinstance(q.get('provider'),str) or not q['provider'].strip(): continue
            if q.get('license_allowed') is not True or q.get('verified') is not True: continue
            age=q['age_seconds']; quality=q['quality']
            if isinstance(age,bool) or isinstance(quality,bool) or not isinstance(age,(int,float)) or not isinstance(quality,(int,float)): continue
            if not (0<=age<=max_age_seconds and min_quality<=quality<=1): continue
            parts=[Decimal(str(q[k])) for k in ('source_usd','tokens_usd','network_usd')]
            if any(not p.is_finite() or p<0 for p in parts): continue
            cost=sum(parts)
            if not cost.is_finite() or cost<0 or cost>Decimal(str(max_total_usd)): continue
            eligible.append((cost,-quality,q['provider'],q))
        except (KeyError,TypeError,ValueError,InvalidOperation): continue
    if not eligible: return {'status':'no_eligible_quote','selected':None}
    cost,_,_,q=min(eligible,key=lambda x:x[:3])
    return {'status':'selected','selected':q['provider'],'total_usd':str(cost),'source':q.get('source_url')}
