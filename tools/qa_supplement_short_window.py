"""Exact exported-table reconciliation and read-only PDF/raster checks for S4."""
from collections import Counter,defaultdict
import csv
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/supplement/short-window-posthoc-v1'
def rows(name):
    with (OUT/name).open(encoding='utf-8',newline='') as f: return list(csv.DictReader(f))
def key(r): return tuple(str(r[k]) for k in ['phase','node_count','window','scope','comparison','metric'])
def fraction(r,name): return Fraction(int(r[name+'_numerator']),int(r[name+'_denominator']))

def main():
    result=json.loads((OUT/'results.json').read_bytes()); expected={key(r):r for r in result['contrasts']}
    changed={key(r):r for r in result['window_changes']}
    for name,lookup in [('window-contrasts.csv',expected),('paired-window-changes.csv',changed)]:
        data=rows(name); assert len(data)==len(lookup) and len({key(r) for r in data})==len(data)
        for r in data:
            target=lookup[key(r)]
            for m in ['estimate','lower','upper']:
                if m in target['exact']:
                    assert fraction(r,m)==Fraction(*target['exact'][m])
                    assert float(r[m])==target['display'][m]
                else: assert r[m]==r[m+'_numerator']==r[m+'_denominator']==''
    parent=rows('parent-window-contrasts.csv'); assert len(parent)==28800
    totals=defaultdict(Fraction); counts=Counter()
    for r in parent: totals[key(r)]+=Fraction(int(r['numerator']),int(r['denominator'])); counts[key(r)]+=1
    assert len(totals)==480 and set(counts.values())=={60}
    for k,value in totals.items(): assert value/60==Fraction(*expected[k]['exact']['estimate'])
    absolute=rows('absolute-window-means.csv'); assert len(absolute)==384
    av={tuple(r[k] for k in ['phase','node_count','window','scope','family','role']):r for r in absolute}
    assert len(av)==384
    for r in result['contrasts']:
        pre=tuple(str(r[k]) for k in ['phase','node_count','window','scope'])
        if r['comparison']=='DA-minus-FHS5': a,b=av[pre+('demand-aware','source')],av[pre+('fhs5','source')]
        else:
            family=r['comparison'].split('-minus-matched-binary')[0]
            a,b=av[pre+(family,'source')],av[pre+(family,'binary_panel')]
        metric='normalized_restricted_time' if r['metric']=='normalized_restricted_tau_nopath' else 'failure_risk'
        assert fraction(a,metric)-fraction(b,metric)==Fraction(*r['exact']['estimate'])
    for r in result['window_changes']:
        k=list(key(r)); k[2]='half'; half=Fraction(*expected[tuple(k)]['exact']['estimate']); k[2]='full'
        assert half-Fraction(*expected[tuple(k)]['exact']['estimate'])==Fraction(*r['exact']['estimate'])
    events=rows('saved-event-observations.csv'); assert len(events)==28238
    identities={(r['phase'],r['parent_graph_id'],r['regime_id'],r['variant_id']) for r in events}; assert len(identities)==len(events)
    assert len({(r['phase'],r['parent_graph_id']) for r in events})==480
    pairs=defaultdict(dict)
    for r in events:
        flag=int(r['saved_observed']); t=int(r['saved_request_index']); H=int(r['original_horizon']); h=int(r['half_horizon'])
        assert flag in [0,1] and 0<=t<=H and (flag or t==H)
        assert int(r['half_restricted_time'])==min(t,h) and int(r['half_observed'])==int(flag and t<=h)
        assert int(r['full_restricted_time'])==t and int(r['full_observed'])==flag
        pairs[r['phase'],r['node_count'],r['parent_graph_id'],r['regime_id']][r['variant_id']]=r
    assert len(pairs)==3360
    info=defaultdict(lambda:[0,0,0,0,0]); timing=defaultdict(Fraction)
    panels={}
    for path in (OUT/'parents').glob('*.json'):
        p=json.loads(path.read_bytes())['payload']; panels[p['phase'],p['parent_graph_id']]=p['panels']
    for (phase,n,parent,rid),variants in pairs.items():
        da,fh=variants['demand-aware'],variants['fhs5']
        for w in ['half','full']:
            df,ff=int(da[w+'_observed']),int(fh[w+'_observed'])
            values=[1,int(not df and not ff),int(bool(df or ff)),int(da[w+'_restricted_time']!=fh[w+'_restricted_time']),int(df!=ff)]
            dest=info[phase,n,w]
            for j,x in enumerate(values): dest[j]+=x
        for family,ids in panels[phase,parent].items():
            for role,references in [('source',[family]),('binary_panel',ids)]:
                for vid in references:
                    e=variants[vid]; flag=int(e['saved_observed']); t=int(e['saved_request_index']); h=int(e['half_horizon'])
                    cat='original-administrative-censor' if not flag else 'before-half' if t<h else 'at-half' if t==h else 'after-half-through-full'
                    timing[phase,n,family,role,cat]+=Fraction(1,len(references))
    for r in rows('DA-FHS5-paired-information.csv'):
        assert info[r['phase'],r['node_count'],r['window']]==[int(r[k]) for k in ['trace_pairs','both_no_event_within_window','at_least_one_observed_event','nonzero_time_difference_pairs','nonzero_risk_difference_pairs']]
    for r in rows('event-timing-summary.csv'):
        k=tuple(r[q] for q in ['phase','node_count','family','role','category'])
        assert timing[k]==fraction(r,'weighted_trace_count')
    preflight=json.loads((OUT/'figure-source-preflight.json').read_bytes()); assert preflight['summary']['counts']['FAIL']==0
    manual=(OUT/'figure-qa.md').read_text(encoding='utf-8'); assert '人工目视通过' in manual
    formats=[]
    for name,height in [('S4-matched-binary-window-effects',190),('S4-DA-FHS5-window-effects-and-changes',115)]:
        pdf=PdfReader(OUT/(name+'.pdf')); assert len(pdf.pages)==1
        page=pdf.pages[0]; width_mm=float(page.mediabox.width)*25.4/72; height_mm=float(page.mediabox.height)*25.4/72
        assert abs(width_mm-170)<1e-7 and abs(height_mm-height)<1e-7 and len(page.extract_text())>400
        for font in page['/Resources']['/Font'].values():
            f=font.get_object(); assert f['/Subtype']=='/Type0'
            assert '/FontFile2' in f['/DescendantFonts'][0].get_object()['/FontDescriptor']
        svg=ET.parse(OUT/(name+'.svg')); assert len(list(svg.iter('{http://www.w3.org/2000/svg}text')))>20
        for ext,dpi in [('tiff',600),('png',300)]:
            with Image.open(OUT/(name+'.'+ext)) as im:
                assert all(abs(v-dpi)<.01 for v in im.info['dpi'])
                assert abs(im.width/dpi*25.4-170)<.1 and abs(im.height/dpi*25.4-height)<.1
        formats.append({'name':name,'pdf_width_mm':width_mm,'pdf_height_mm':height_mm,'pdf_fonts':'embedded TrueType, selectable text',
                        'svg_text':'editable','tiff_dpi':600,'png_dpi':300})
    names=['window-contrasts.csv','paired-window-changes.csv','parent-window-contrasts.csv','saved-event-observations.csv',
           'absolute-window-means.csv','event-timing-summary.csv','DA-FHS5-paired-information.csv','figure-qa.md','results.json']
    names.extend(f['name']+'.'+ext for f in formats for ext in ['svg','pdf','tiff','png'])
    proof={'status':'passed-visual-and-source-QA','exact_CSV_reconciliation':True,'csv_window_rows':480,'csv_change_rows':240,
           'csv_parent_rows':28800,'csv_event_rows':28238,'csv_absolute_rows':384,'paired_trace_measurements':3360,
           'formats':formats,'source_preflight':preflight['summary'],'manual_visual_inspection':'Both final matplotlib PNGs inspected; no clipped labels or overlapping panels.',
           'QA_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'files':{name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in names}}
    (OUT/'figure-qa.json').write_text(json.dumps(proof,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':proof['status'],'exact_tables':7,'figure_bundles':2}))

if __name__=='__main__': main()
