#!/usr/bin/env python3
"""
Generate viewer.html from index.html + verifier.json + designer.json.

- Content: tagged via verifier.json html_line + context matching
- Assets: tagged via data-des attributes already in HTML + designer.json metadata

Usage:
    python3 tools/verifier/generate_viewer.py PROJECT_DIR
"""

import json
import os
import re
import sys


def find_sentence_positions(html_lines, sentences):
    """Use html_line to find exact line, then find context within that line."""
    line_offsets = [0]
    for line in html_lines:
        line_offsets.append(line_offsets[-1] + len(line))

    results = []
    missed = []

    for i, s in enumerate(sentences):
        ctx = s['context']
        ln = s['html_line']

        if ln < 1 or ln > len(html_lines):
            missed.append((i, ctx[:50], f'line {ln} out of range'))
            continue

        line_text = html_lines[ln - 1]
        col = line_text.find(ctx)

        if col != -1:
            char_pos = line_offsets[ln - 1] + col
            results.append((char_pos, len(ctx), i))
            continue

        found = False
        for delta in range(-3, 4):
            check_ln = ln + delta
            if check_ln < 1 or check_ln > len(html_lines) or delta == 0:
                continue
            line_text = html_lines[check_ln - 1]
            col = line_text.find(ctx)
            if col != -1:
                char_pos = line_offsets[check_ln - 1] + col
                results.append((char_pos, len(ctx), i))
                found = True
                break

        if not found:
            short = ctx[:50]
            line_text = html_lines[ln - 1]
            col = line_text.find(short)
            if col != -1:
                char_pos = line_offsets[ln - 1] + col
                results.append((char_pos, len(short), i))
            else:
                missed.append((i, ctx[:50], f'not found near line {ln}'))

    return results, missed


def extract_assets_from_html(html):
    """Find all data-des elements and their tag/attributes."""
    assets = []
    seen = set()
    for m in re.finditer(r'<(\w+)\s[^>]*data-des="([^"]+)"[^>]*>', html):
        tag = m.group(1)
        des_id = m.group(2)
        if des_id in seen:
            continue
        seen.add(des_id)

        # Extract other useful attrs
        src = ''
        src_m = re.search(r'src="([^"]*)"', m.group(0))
        if src_m:
            src = src_m.group(1)
        cls = ''
        cls_m = re.search(r'class="([^"]*)"', m.group(0))
        if cls_m:
            cls = cls_m.group(1)
        ana = ''
        ana_m = re.search(r'data-ana="([^"]*)"', m.group(0))
        if ana_m:
            ana = ana_m.group(1)

        # Determine visual type
        vtype = 'visual'
        if tag == 'img':
            vtype = 'image'
        elif tag == 'video':
            vtype = 'video'
        elif 'stat' in cls:
            vtype = 'stat'
        elif 'chart' in cls or 'chart' in des_id:
            vtype = 'chart'

        line_num = html[:m.start()].count('\n') + 1

        assets.append({
            'des_id': des_id,
            'tag': tag,
            'type': vtype,
            'src': src,
            'ana': ana,
            'line': line_num,
        })
    return assets


def inject_tags(html, positions):
    """Insert sentence ID tags. Process bottom to top."""
    positions.sort(key=lambda x: x[0], reverse=True)
    for char_pos, length, idx in positions:
        sid = idx + 1
        tag = (
            f'<span class="_ev" id="_s{sid}" '
            f'style="display:none;font-size:8px;font-family:monospace;font-weight:700;'
            f'color:#6ee7b7;background:#064e3b;padding:0 3px;border-radius:2px;'
            f'margin-right:3px;vertical-align:super;cursor:pointer" '
            f'data-i="{idx}">{sid}</span>'
        )
        html = html[:char_pos] + tag + html[char_pos:]
    return html


def inject_asset_badges(html, assets, designer_items):
    """Inject yellow badges on data-des elements. Badge shows index number matching right panel."""
    # Build ordered list of des_ids matching designer_items key order
    des_order = list(designer_items.keys())

    replacements = []
    for asset in assets:
        des_id = asset['des_id']
        pattern = f'data-des="{des_id}"'
        pos = html.find(pattern)
        if pos == -1:
            continue
        tag_end = html.find('>', pos)
        if tag_end == -1:
            continue
        # Get index in designer items (1-based)
        idx = des_order.index(des_id) + 1 if des_id in des_order else 0
        label = str(idx) if idx > 0 else des_id
        replacements.append((tag_end + 1, des_id, label))

    replacements.sort(key=lambda x: x[0], reverse=True)
    for insert_pos, des_id, label in replacements:
        badge = (
            f'<span class="_eva" '
            f'style="display:none;position:absolute;top:4px;left:4px;font-size:9px;'
            f'font-family:monospace;font-weight:700;color:#fbbf24;'
            f'background:rgba(120,53,15,.85);padding:2px 6px;border-radius:4px;'
            f'z-index:100;cursor:pointer;backdrop-filter:blur(4px)" '
            f'data-des="{des_id}">{label}</span>'
        )
        html = html[:insert_pos] + badge + html[insert_pos:]
    return html


def inject_style(html):
    """Inject CSS into <head>."""
    css = '''<style id="_ev_styles">
#_ev_bulb{position:fixed;bottom:24px;right:24px;z-index:99999;width:48px;height:48px;border-radius:50%;background:#1a1a2e;color:#6ee7b7;border:2px solid #6ee7b7;font-size:22px;cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:0 4px 16px rgba(0,0,0,0.4);transition:all 0.2s}
#_ev_bulb:hover{transform:scale(1.1)}
#_ev_bulb.on{background:#6ee7b7;color:#1a1a2e;right:460px}
#_ev_side{position:fixed;top:0;right:0;width:0;height:100vh;overflow:hidden;background:#111827;border-left:2px solid #0f3460;color:#e0e0e0;transition:width 0.3s;z-index:99998;font-family:system-ui,sans-serif;font-size:13px}
#_ev_side.open{width:440px;overflow-y:auto}
body._ev_open{margin-right:440px;transition:margin-right 0.3s}
#_ev_side::-webkit-scrollbar{width:6px}#_ev_side::-webkit-scrollbar-thumb{background:#334;border-radius:3px}
._ev_hdr{position:sticky;top:0;z-index:1;background:#16213e;border-bottom:1px solid #0f3460}
._ev_bar{padding:10px 16px;font-size:11px;color:#8899aa}._ev_bar b{color:#6ee7b7}
._ev_tabs{display:flex;border-top:1px solid #0f3460}
._ev_tab{flex:1;padding:8px 0;text-align:center;font-size:11px;color:#6b7280;cursor:pointer;border-bottom:2px solid transparent;transition:all 0.15s}
._ev_tab:hover{color:#e0e0e0}
._ev_tab.on{color:#6ee7b7;border-bottom-color:#6ee7b7}
._ev_ls{padding:8px 12px}
._ev_row{padding:6px 10px;margin-bottom:2px;border-radius:6px;cursor:pointer;border-left:3px solid #0f3460;background:#16213e;display:flex;gap:8px;align-items:flex-start;transition:all 0.15s}
._ev_row:hover{background:#1e293b;border-left-color:#60a5fa}._ev_row.on{border-left-color:#6ee7b7;background:#1e293b}
._ev_row.asset{border-left-color:#78350f}._ev_row.asset:hover{border-left-color:#fbbf24}._ev_row.asset.on{border-left-color:#fbbf24;background:#1e293b}
._ev_rid{flex-shrink:0;font-size:9px;font-family:monospace;font-weight:700;color:#6ee7b7;background:#064e3b;padding:1px 5px;border-radius:3px;margin-top:2px;min-width:22px;text-align:center}
._ev_rid.asset{color:#fbbf24;background:#78350f}
._ev_rtxt{flex:1;font-size:12px;color:#d1d5db;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
._ev_rmeta{font-size:9px;color:#4b5563;font-family:monospace;margin-top:2px}
._ev_chips{display:flex;flex-wrap:wrap;gap:2px;margin-top:2px}
._ev_c{font-size:9px;padding:0 4px;border-radius:2px;font-family:monospace;font-weight:600}
._ev_c.ana{background:#064e3b;color:#6ee7b7}._ev_c.det{background:#4a1d6e;color:#c4b5fd}._ev_c.des{background:#78350f;color:#fbbf24}._ev_c.edt{background:#1e3a5f;color:#93c5fd}
._ev_det{display:none;padding:8px 10px;background:#1a2332;border-radius:0 0 6px 6px;margin:-2px 0 4px 34px}._ev_det.open{display:block}
._ev_ctx{font-size:13px;color:#e0e0e0;line-height:1.6;margin-bottom:8px;border-left:3px solid #60a5fa;padding-left:10px}
._ev_ctx.asset{border-left-color:#fbbf24}
._ev_sum{background:#16213e;border-radius:6px;padding:8px 10px;margin-bottom:8px;font-size:11px;color:#93c5fd;line-height:1.5}
._ev_atype{font-size:9px;padding:1px 6px;border-radius:3px;font-weight:600;margin-right:6px}
._ev_atype.chart{background:#1e3a5f;color:#93c5fd}._ev_atype.image{background:#4a1d6e;color:#c4b5fd}._ev_atype.video{background:#78350f;color:#fbbf24}._ev_atype.stat{background:#064e3b;color:#6ee7b7}._ev_atype.visual{background:#374151;color:#d1d5db}
</style>'''
    return html.replace('<head>', '<head>\n' + css, 1)


def inject_script(html, verifier_json_str, designer_json_str):
    """Inject button + side panel + JS before </body>."""
    script = '''<button id="_ev_bulb">&#128269;</button>
<div id="_ev_side">
  <div class="_ev_hdr">
    <div class="_ev_bar" id="_ev_bar"></div>
    <div class="_ev_tabs"><div class="_ev_tab on" id="_tab_s" onclick="_evTab('s')">Content</div><div class="_ev_tab" id="_tab_a" onclick="_evTab('a')">Assets</div></div>
  </div>
  <div class="_ev_ls" id="_ev_ls_s"></div>
  <div class="_ev_ls" id="_ev_ls_a" style="display:none"></div>
</div>
<script>
try{
var _evOn=false;
var V=''' + verifier_json_str + ''';
var D=''' + designer_json_str + ''';
document.getElementById("_ev_bulb").addEventListener("click",function(){
  _evOn=!_evOn;
  document.getElementById("_ev_bulb").classList.toggle("on",_evOn);
  document.getElementById("_ev_side").classList.toggle("open",_evOn);
  document.body.classList.toggle("_ev_open",_evOn);
  var t=document.querySelectorAll("._ev");for(var j=0;j<t.length;j++)t[j].style.display=_evOn?"inline":"none";
  t=document.querySelectorAll("._eva");for(var j=0;j<t.length;j++)t[j].style.display=_evOn?"inline":"none";
});
document.addEventListener("click",function(e){
  if(e.target.classList.contains("_ev")){e.stopPropagation();if(!_evOn)document.getElementById("_ev_bulb").click();_evTab("s");_evOpenRow(parseInt(e.target.getAttribute("data-i")),"s");}
  if(e.target.classList.contains("_eva")){e.stopPropagation();if(!_evOn)document.getElementById("_ev_bulb").click();var did=e.target.getAttribute("data-des");_evTab("a");_evOpenAsset(did);}
});
(function(){
  document.getElementById("_ev_bar").innerHTML="<b>"+V.stats.traced+"</b>/"+V.stats.total_sentences+" sentences &middot; <b>"+Object.keys(D).length+"</b> assets";
  var h="";
  for(var i=0;i<V.sentences.length;i++){var s=V.sentences[i];var chips="";
    for(var k=0;k<s.retrieve.length;k++){var rid=s.retrieve[k];chips+='<span class="_ev_c '+rid.split("_")[0]+'">'+rid+"</span>";}
    h+='<div class="_ev_row" id="_r'+i+'" onclick="_evOpenRow('+i+',\\'s\\')"><span class="_ev_rid">'+(i+1)+'</span><div style="flex:1;min-width:0"><div class="_ev_rtxt">'+_evEsc(s.context)+'</div><div class="_ev_rmeta">L'+s.html_line+'</div><div class="_ev_chips">'+chips+'</div></div></div>';
    h+='<div class="_ev_det" id="_d'+i+'"><div class="_ev_ctx">'+_evEsc(s.context)+'</div><div class="_ev_sum">'+_evEsc(s.summary)+'</div></div>';}
  document.getElementById("_ev_ls_s").innerHTML=h;
  var ha="";var dkeys=Object.keys(D);
  for(var i=0;i<dkeys.length;i++){var did=dkeys[i];var a=D[did];
    var chips='<span class="_ev_c des">'+did+'</span>';
    if(a.data_source){var ds=a.data_source;if(typeof ds==="string")ds=[ds];for(var k=0;k<ds.length;k++)chips+='<span class="_ev_c ana">'+ds[k]+'</span>';}
    if(a.based_on)for(var k=0;k<a.based_on.length;k++)chips+='<span class="_ev_c ana">'+a.based_on[k]+'</span>';
    ha+='<div class="_ev_row asset" id="_ra_'+did+'" onclick="_evOpenAsset(\\''+did+'\\')"><span class="_ev_rid asset">'+(i+1)+'</span><div style="flex:1;min-width:0"><span class="_ev_atype '+a.type+'">'+a.type+'</span><span class="_ev_rtxt">'+_evEsc(a.label)+'</span><div class="_ev_chips">'+chips+'</div></div></div>';
    ha+='<div class="_ev_det" id="_da_'+did+'"><div class="_ev_ctx asset">'+_evEsc(a.label)+'</div><div class="_ev_sum">'+_evEsc(a.brief||"")+'</div><div class="_ev_rmeta">type: '+a.type+(a.data_source?" | data: "+a.data_source:"")+'</div></div>';}
  document.getElementById("_ev_ls_a").innerHTML=ha;
})();
}catch(err){document.getElementById("_ev_bar").innerHTML="<span style=color:red>"+err.message+"</span>"}
function _evTab(t){
  document.getElementById("_tab_s").classList.toggle("on",t==="s");
  document.getElementById("_tab_a").classList.toggle("on",t==="a");
  document.getElementById("_ev_ls_s").style.display=t==="s"?"block":"none";
  document.getElementById("_ev_ls_a").style.display=t==="a"?"block":"none";
}
function _evOpenRow(i){
  var r=document.getElementById("_r"+i),d=document.getElementById("_d"+i);
  var wasOpen=d&&d.classList.contains("open");
  var a=document.querySelectorAll("._ev_det.open");for(var j=0;j<a.length;j++)a[j].classList.remove("open");
  a=document.querySelectorAll("._ev_row.on");for(var j=0;j<a.length;j++)a[j].classList.remove("on");
  if(!wasOpen&&r&&d){r.classList.add("on");d.classList.add("open");r.scrollIntoView({behavior:"smooth",block:"center"});
    var t=document.getElementById("_s"+(i+1));if(t)t.scrollIntoView({behavior:"smooth",block:"center"});}
}
function _evOpenAsset(did){
  var r=document.getElementById("_ra_"+did),d=document.getElementById("_da_"+did);
  var wasOpen=d&&d.classList.contains("open");
  var a=document.querySelectorAll("._ev_det.open");for(var j=0;j<a.length;j++)a[j].classList.remove("open");
  a=document.querySelectorAll("._ev_row.on");for(var j=0;j<a.length;j++)a[j].classList.remove("on");
  if(!wasOpen&&r&&d){r.classList.add("on");d.classList.add("open");r.scrollIntoView({behavior:"smooth",block:"center"});
    var el=document.querySelector('[data-des="'+did+'"]');if(el)el.scrollIntoView({behavior:"smooth",block:"center"});}
}
function _evEsc(s){return(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
</script>'''
    return html.replace('</body>', script + '\n</body>', 1)


def main():
    proj = sys.argv[1].rstrip('/')

    html_path = os.path.join(proj, 'index.html')
    verifier_path = os.path.join(proj, 'verifier.json')
    designer_path = os.path.join(proj, 'designer.json')

    with open(html_path, encoding='utf-8') as f:
        html = f.read()
    html_lines = html.splitlines(keepends=True)

    with open(verifier_path, encoding='utf-8') as f:
        V = json.load(f)

    # Load designer.json for asset metadata
    designer = {}
    if os.path.exists(designer_path):
        with open(designer_path, encoding='utf-8') as f:
            designer = json.load(f)

    sentences = V['sentences']

    # Step 1: Find sentence positions
    positions, missed = find_sentence_positions(html_lines, sentences)
    print(f'Content matched: {len(positions)}/{len(sentences)}')
    if missed:
        print(f'Missed: {len(missed)}')
        for idx, ctx, reason in missed[:5]:
            print(f'  #{idx+1}: "{ctx}" — {reason}')

    # Step 2: Extract assets from HTML
    assets = extract_assets_from_html(html)
    print(f'Assets found: {len(assets)}')

    # Step 3: Inject sentence tags (bottom-up)
    html = inject_tags(html, positions)

    # Step 4: Inject asset badges (bottom-up)
    html = inject_asset_badges(html, assets, designer.get('items', {}))

    # Step 5: Inject style into <head>
    html = inject_style(html)

    # Step 6: Build lite JSONs and inject script
    V_lite = {
        'stats': V['stats'],
        'sentences': [
            {
                'context': s['context'],
                'html_line': s['html_line'],
                'summary': s['summary'],
                'retrieve': s['retrieve'],
            }
            for s in V['sentences']
        ],
    }
    v_str = json.dumps(V_lite, ensure_ascii=True)
    v_str = v_str.replace('</script>', '<\\/script>')

    # Designer lite: des_id -> {label, type, brief, data_source, based_on}
    D_lite = {}
    items = designer.get('items', {})
    for des_id, item in items.items():
        D_lite[des_id] = {
            'label': item.get('label', des_id),
            'type': item.get('type', 'visual'),
            'brief': (item.get('brief', '') or '')[:300],
            'data_source': item.get('content', {}).get('data_source', ''),
            'based_on': item.get('based_on', []),
        }
    d_str = json.dumps(D_lite, ensure_ascii=True)
    d_str = d_str.replace('</script>', '<\\/script>')

    html = inject_script(html, v_str, d_str)

    # Write
    out_path = os.path.join(proj, 'viewer.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'viewer.html written to {out_path}')


if __name__ == '__main__':
    main()
