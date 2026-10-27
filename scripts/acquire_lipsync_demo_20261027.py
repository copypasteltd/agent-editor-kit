"""Acquire an attributed public-domain painting for the actual lip-sync case."""
from pathlib import Path
import hashlib,io,json,urllib.parse
from acquire_lipsync_20261027 import ROOT,BASE,fetch,save
from PIL import Image,ImageCms
title='File:Mona Lisa, by Leonardo da Vinci, from C2RMF retouched.jpg'
api='https://commons.wikimedia.org/w/api.php?'+urllib.parse.urlencode(dict(action='query',titles=title,
    prop='imageinfo',iiprop='url|extmetadata',iiurlwidth=960,format='json'))
p=BASE/'commons-source.json'
if not p.exists():save(p,fetch(api))
value=json.loads(p.read_bytes());entry=next(iter(value['query']['pages'].values()))['imageinfo'][0]
metadata=entry['extmetadata'];license=metadata.get('LicenseShortName',{}).get('value','')
assert 'public domain' in license.lower() or metadata.get('Copyrighted',{}).get('value')=='False',(license,metadata.get('Copyrighted'))
out=ROOT/'docs/assets/native-lipsync-20261027-r1';out.mkdir(parents=True,exist_ok=True)
source=out/'painting-original.jpg'
if not source.exists():save(source,fetch(entry['thumburl']))
with Image.open(source) as im:
    if im.info.get('icc_profile'):
        original=ImageCms.ImageCmsProfile(io.BytesIO(im.info['icc_profile']))
        im=ImageCms.profileToProfile(im,original,ImageCms.createProfile('sRGB'),outputMode='RGB')
    else:im=im.convert('RGB')
    # Public 960px thumbnail, explicit 2D source crop; the painting remains
    # distinct from any real person/audio identity.
    image=im.crop((175,80,815,720)).resize((512,512),Image.Resampling.LANCZOS)
    image.save(out/'portrait.png')
record={'source_page':entry['descriptionurl'],'source_url':entry['thumburl'],'artist':'Leonardo da Vinci (1452–1519)',
    'license':license,'raw_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'portrait_sha256':hashlib.sha256((out/'portrait.png').read_bytes()).hexdigest(),
    'preprocessing':'ICC-to-sRGB when present; crop(175,80,815,720), resize512 Lanczos',
    'purpose':'Clearly labeled synthetic audio animation of a public-domain painting; no authentic recording claim'}
save(BASE/'demo-source.json',(json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps(record,ensure_ascii=False))
