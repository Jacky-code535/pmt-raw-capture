#!/usr/bin/env python3
"""Build an offline, selectable XML-local Core dashboard from derived CSVs."""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

KEY_METRICS = ("temperature_c", "core_usage_delta", "pvp64_rate", "pvp1024_rate",
               "frequency_all_mhz", "voltage_all_mv", "c6_histogram_pct")


def build_data(root):
    configuration = json.loads((root / "metrics.json").read_text(encoding="utf-8"))
    definitions = {}
    for definition in configuration["metrics"]:
        if definition["id"] in KEY_METRICS:
            definitions[definition["id"]] = definition["title"]
    if not definitions:
        for definition in configuration["metrics"]:
            if definition["operation"] != "histogram_distribution" and len(definitions) < 7:
                definitions[definition["id"]] = definition["title"]
    sequences = set()
    with (root / "core-metrics.csv").open(newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            if row["metric"] in definitions:
                sequences.add(int(row["sequence"]))
    ordered = sorted(sequences)
    stride = max(1, (len(ordered) + 599) // 600)
    selected = set(ordered[::stride]) | ({ordered[-1]} if ordered else set())
    frames = defaultdict(dict)
    with (root / "core-metrics.csv").open(newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            if row["metric"] not in definitions:
                continue
            sequence = int(row["sequence"])
            if sequence not in selected:
                continue
            scope = row["scope"]
            frame = frames[scope].setdefault(sequence, {"end": row["end"], "metrics": {}})
            if frame["end"] != row["end"] or row["metric"] in frame["metrics"]:
                raise ValueError("inconsistent or duplicated core metric row")
            frame["metrics"][row["metric"]] = [float(row["value"]) if row["value"] else None, row["quality"]]
    summaries = defaultdict(dict)
    with (root / "metric-summary.csv").open(newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            if row["level"] == "core" and row["metric"] in definitions:
                summaries[row["scope"]][row["metric"]] = float(row["aggregate"]) if row["aggregate"] else None
    result = {}
    for scope, samples in frames.items():
        if not summaries[scope] or any(set(frame["metrics"]) != set(definitions) for frame in samples.values()):
            raise ValueError("incomplete derived metrics for " + scope)
        result[scope] = {"samples": [[sequence, samples[sequence]["end"], samples[sequence]["metrics"]]
                                     for sequence in sorted(samples)], "aggregate": summaries[scope]}
    if not result:
        raise ValueError("no Core metrics to display")
    return {"scopes": result, "definitions": definitions, "histograms": {}}


PAGE = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PMT 逐 Core 指标看板</title>
<style>
:root{--ink:#233732;--muted:#567067;--line:#d2dfd7;--green:#147c68;--rust:#bb5b40;--blue:#347994}
*{box-sizing:border-box}body{margin:0;background:#edf2ee;color:var(--ink);font-family:"Noto Sans CJK SC","Microsoft YaHei",sans-serif;line-height:1.5}
header{background:#143c33;color:#f5faf6;padding:24px max(18px,calc((100vw - 1150px)/2))}header a{color:#c5e9d9}h1{font-size:29px;margin:6px 0}h2{font-size:19px;margin:0 0 8px}h3{font-size:15px;margin:0 0 6px}p{margin:6px 0 12px}
main{max-width:1150px;margin:auto;padding:20px 18px 70px}.subtitle{color:#d1e3d8;font-size:14px}.controls{display:flex;flex-wrap:wrap;gap:15px;padding:16px 0;border-bottom:1px solid var(--line)}
label{display:grid;gap:4px;font-size:13px;font-weight:700;min-width:130px}select{padding:8px 10px;border:1px solid #a4b8aa;background:white;border-radius:3px;color:var(--ink);font:inherit;font-size:14px;max-width:100%}select:focus-visible,a:focus-visible{outline:2px solid var(--green);outline-offset:2px}
.context{font-size:13px;color:var(--muted);margin:13px 0 18px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 24px}section{border-top:1px solid var(--line);padding:20px 0}figure{margin:0 0 22px;min-width:0}figcaption{font-weight:700;font-size:14px;margin-bottom:3px}.detail{color:var(--muted);font-size:12px;min-height:35px}.chart{background:white;border:1px solid var(--line);width:100%;height:auto;aspect-ratio:720/238}.axis{fill:#52675e;font-size:11px;font-family:sans-serif}.empty{padding:48px 10px;text-align:center;background:white;border:1px solid var(--line);color:var(--muted)}
.bins{display:flex;gap:4px;background:white;border:1px solid var(--line);height:234px;padding:12px 8px 8px}.bin{flex:1;min-width:0;text-align:center;display:flex;flex-direction:column}.bin-space{flex:1;border-bottom:1px solid var(--line);display:flex;align-items:end;justify-content:center}.bar{width:80%;min-height:1px;background:var(--green)}.bin-label{font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--muted);height:17px}
.bucket-table{width:100%;border-collapse:collapse;background:white;font-size:13px}.bucket-table td{border-bottom:1px solid var(--line);padding:5px 9px}.bucket-table td:last-child{text-align:right;font-variant-numeric:tabular-nums}details{margin-top:6px}summary{cursor:pointer;color:var(--green);font-weight:700;font-size:13px}
.notice{background:#fff;border-left:3px solid #bd833d;padding:12px;font-size:13px;margin:10px 0 18px}.stats{display:flex;gap:24px;flex-wrap:wrap}.stat{min-width:160px}.stat strong{display:block;font-size:23px;color:var(--green)}.stat span{font-size:12px;color:var(--muted)}
@media(max-width:740px){h1{font-size:24px}.grid{grid-template-columns:1fr}.controls label{flex:1 1 135px}main{padding:14px 15px 55px}}
</style></head><body>
<header><a href="pmt-report.xlsx">下载 Excel 汇总</a><h1>逐 Core 指标看板</h1><p class="subtitle">本地离线 CSV → JSON 派生指标 → 可选择 aggregator 和 XML 本地 Core 的图表</p></header>
<main><div class="controls"><label>Aggregator<select id="aggregator"></select></label><label>XML 本地 Core<select id="core"></select></label></div>
<p id="identity" class="context"></p><div class="notice">这里选的是 PMT XML 本地槽位，不是 Linux CPU 编号或已确认的物理 Core。百分比分布及加权频率/电压为探索性结果；此离线视图逐相邻样本计算，与在线 dashboard 的滚动 5 分钟 Prometheus 查询不能直接逐点对比。</div>
<section><h2>选定 Core 的概况</h2><div class="stats" id="stats"></div></section>
<section><h2>温度与活动</h2><div class="grid" id="activity"></div></section>
<section><h2>频率与电压估计</h2><div class="grid" id="operating"></div></section>
<section><h2>指标口径</h2><p>core_usage 是 XML 定义的实验性累计量，增量不是 CPU 利用率；PVP 64/1024-cycle 是两种独立检测窗口的累计 counter；频率 r0 是 C6，电压 r0 是 &lt;602 mV。首个 counter 样本只有基线。图表最多显示约 600 个实际采样点，不插值；全部指标、直方图和质量原因见 <a href="core-metrics.csv">Core 指标 CSV</a>，统计见 <a href="metric-summary.csv">指标摘要</a>，计算定义见 <a href="metrics.json">JSON</a>。</p></section>
</main><script id="report-data" type="application/json">__DATA__</script><script>
"use strict";
const data=JSON.parse(document.getElementById('report-data').textContent), allScopes=Object.keys(data.scopes).sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
const agg=document.getElementById('aggregator'),core=document.getElementById('core');
const metricNames={temperature_c:'温度',core_usage_lifetime:'Core usage 累计量',core_usage_delta:'Core usage 区间增量',pvp64_delta:'PVP 64-cycle 区间增量',pvp64_rate:'PVP 64-cycle 速率',pvp1024_delta:'PVP 1024-cycle 区间增量',pvp1024_rate:'PVP 1024-cycle 速率',frequency_all_mhz:'含 C6 加权频率',frequency_non_c6_mhz:'非 C6 加权频率',voltage_all_mv:'全桶加权电压',c6_histogram_pct:'频率 C6 桶占比'};
const descriptions={core_usage_lifetime:'实验性累计量，不是 CPU 使用率',core_usage_delta:'相邻快照增量，不是在线 5 分钟增加量',frequency_all_mhz:'C6(r0)按 0 MHz 纳入；非瞬时频率',frequency_non_c6_mhz:'仅非 C6 桶，非瞬时频率',voltage_all_mv:'包含低于 602 mV 的 r0；非瞬时电压',c6_histogram_pct:'直方图占比，非校准后的 CPU 利用率'};
const groupNames={frequency_distribution:'频率桶分布',voltage_distribution:'电压桶分布',temperature_distribution:'温度桶分布'};
const units={temperature_c:'°C',core_usage_lifetime:'core_usage',core_usage_delta:'core_usage',pvp64_delta:'次',pvp64_rate:'次/秒',pvp1024_delta:'次',pvp1024_rate:'次/秒',frequency_all_mhz:'MHz',frequency_non_c6_mhz:'MHz',voltage_all_mv:'mV',c6_histogram_pct:'%'};
const $=id=>document.getElementById(id), scopesFor=aggregator=>allScopes.filter(scope=>scope.split('/')[1]===aggregator);
function option(select,value,text){const element=document.createElement('option');element.value=value;element.textContent=text;select.append(element)}
function metric(sample,id){return sample[2][id]||[null,'missing_input']}
function selectedScope(){return allScopes.find(scope=>scope.split('/')[1]===agg.value && scope.split('/')[2]===core.value)}
function syncCores(){const current=core.value;core.replaceChildren();for(const scope of scopesFor(agg.value))option(core,scope.split('/')[2],scope.split('/')[2]);core.value=[...core.options].some(o=>o.value===current)?current:'C0';render()}
function textNumber(value,digits=2){if(value===null||value===undefined)return '无有效值';const number=Number(value);return number!==0&&Math.abs(number)<.5*10**-digits?number.toExponential(2):number.toFixed(digits)}
function chart(samples,id,color){const values=samples.map(sample=>metric(sample,id)[0]),valid=values.filter(value=>value!==null && Number.isFinite(value));
 if(!valid.length){const empty=document.createElement('div');empty.className='empty';empty.textContent='没有有效观测；该槽位可能未启用或这一指标没有增长。';return empty}
 let low=Math.min(...valid),high=Math.max(...valid),padding=(high-low)*.12||Math.max(Math.abs(high)*.05,1);low-=padding;high+=padding;
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 720 238');svg.classList.add('chart');svg.setAttribute('role','img');svg.setAttribute('aria-label',metricNames[id]+' 时间趋势');
 const el=(tag,attrs,parent=svg)=>{const node=document.createElementNS(svg.namespaceURI,tag);for(const [key,value] of Object.entries(attrs))node.setAttribute(key,String(value));parent.append(node);return node};
 const x=index=>55+645*index/Math.max(1,values.length-1),y=value=>24+166*(high-value)/(high-low);
 for(let tick=0;tick<=2;tick++){const val=low+(high-low)*tick;el('line',{x1:55,y1:y(val),x2:700,y2:y(val),stroke:'#dce4dd'});el('text',{x:46,y:y(val)+4,'text-anchor':'end',class:'axis'}).textContent=Math.abs(val)<.01&&val!==0?val.toExponential(1):Math.abs(val)<1?val.toFixed(3):val.toFixed(1)}
 for(const index of [0,Math.floor((values.length-1)/2),values.length-1])el('text',{x:x(index),y:223,'text-anchor':'middle',class:'axis'}).textContent=String(samples[index][0]);
 let path=[];function flush(){if(path.length>1)el('polyline',{points:path.join(' '),fill:'none',stroke:color,'stroke-width':2.3});path=[]}
 values.forEach((value,index)=>{if(value===null){flush();return}path.push(x(index)+','+y(value));const dot=el('circle',{cx:x(index),cy:y(value),r:3,fill:color});el('title',{},dot).textContent='序号 '+samples[index][0]+'：'+textNumber(value,4)+' '+units[id]+'（'+metric(samples[index],id)[1]+'）'});flush();return svg}
function figure(container,samples,id,color){const figure=document.createElement('figure'),caption=document.createElement('figcaption'),detail=document.createElement('div');caption.textContent=(metricNames[id]||data.definitions[id])+'（'+(units[id]||'原始单位')+'）';detail.className='detail';const valid=samples.filter(sample=>metric(sample,id)[0]!==null).length;detail.textContent=(descriptions[id]||'相邻样本口径')+' · 有效 '+valid+'/'+samples.length+'，空值不补零';figure.append(caption,detail,chart(samples,id,color));container.append(figure)}
function bins(container,samples,aggregate,id){const figure=document.createElement('figure'),caption=document.createElement('figcaption'),detail=document.createElement('div');caption.textContent=groupNames[id]+'（%）';detail.className='detail';const labels=data.histograms[id],sequence=windowSelect.value;
 let values=labels.map((_,index)=>sequence==='all'?aggregate[id+'.r'+index]:metric(samples.find(sample=>String(sample[0])===sequence),id+'.r'+index)[0]);
 detail.textContent=sequence==='all'?'有效窗口的分子/分母合并；口径 provisional':'相邻样本 '+sequence+' 的直方图占比；口径 provisional';figure.append(caption,detail);
 if(values.some(value=>value===null||!Number.isFinite(value))){const empty=document.createElement('div');empty.className='empty';empty.textContent='该区间暂无有效分布。';figure.append(empty)}else{const plot=document.createElement('div');plot.className='bins';plot.setAttribute('role','img');plot.setAttribute('aria-label',groupNames[id]);const high=Math.max(1,...values);
 labels.forEach((label,index)=>{const column=document.createElement('div'),space=document.createElement('div'),bar=document.createElement('span'),name=document.createElement('span');column.className='bin';space.className='bin-space';bar.className='bar';bar.style.height=(values[index]/high*100)+'%';bar.title=label+'：'+textNumber(values[index])+'%';name.className='bin-label';name.textContent=label;space.append(bar);column.append(space,name);plot.append(column)});figure.append(plot);
 const details=document.createElement('details'),summary=document.createElement('summary'),table=document.createElement('table');summary.textContent='查看各桶数值（四位小数/科学计数）';table.className='bucket-table';labels.forEach((label,index)=>{const row=table.insertRow(),bucket=row.insertCell(),percentage=row.insertCell();bucket.textContent=label;percentage.textContent=textNumber(values[index],4)+' %'});details.append(summary,table);figure.append(details)}container.append(figure)}
function render(){const scope=selectedScope();if(!scope)return;const selected=data.scopes[scope],samples=selected.samples,aggregate=selected.aggregate;
 $('identity').textContent=scope+' · '+samples.length+' 个采样点 · '+samples[0][1]+' 至 '+samples[samples.length-1][1]+' · 物理 Core/Socket 映射未确认';
 $('stats').replaceChildren();for(const [label,id,suffix] of [['平均温度','temperature_c','°C'],['PVP64 总增量','pvp64_delta',' 次'],['含 C6 平均频率','frequency_all_mhz',' MHz'],['平均电压','voltage_all_mv',' mV']]){if(!data.definitions[id])continue;const stat=document.createElement('div'),value=document.createElement('strong'),name=document.createElement('span');stat.className='stat';value.textContent=textNumber(aggregate[id])+(aggregate[id]===null?'':suffix);name.textContent=label;stat.append(value,name);$('stats').append(stat)}
 $('activity').replaceChildren();for(const [id,color] of [['temperature_c','#b4573e'],['core_usage_delta','#147c68'],['pvp64_rate','#397a74'],['pvp1024_rate','#937448']])if(data.definitions[id])figure($('activity'),samples,id,color);
 if(!$('activity').children.length)for(const id of Object.keys(data.definitions))figure($('activity'),samples,id,'#147c68');
 $('operating').replaceChildren();for(const [id,color] of [['frequency_all_mhz','#1b798c'],['voltage_all_mv','#b4573e'],['c6_histogram_pct','#947438']])if(data.definitions[id])figure($('operating'),samples,id,color)}
for(const aggregator of [...new Set(allScopes.map(scope=>scope.split('/')[1]))].sort((a,b)=>a.localeCompare(b,undefined,{numeric:true})))option(agg,aggregator,aggregator);
agg.value=[...agg.options].some(o=>o.value==='telem9')?'telem9':agg.options[0].value;agg.addEventListener('change',syncCores);core.addEventListener('change',render);syncCores();
</script></body></html>'''


def generate(root):
    data = build_data(root)
    serialized = json.dumps(data, ensure_ascii=True, separators=(",", ":"))
    output = root / "逐Core看板.html"
    output.write_text(PAGE.replace("__DATA__", serialized.replace("<", "\\u003c")), encoding="utf-8")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="existing report directory with core-metrics.csv, metric-summary.csv and metrics.json")
    args = parser.parse_args()
    print(generate(args.directory))


if __name__ == "__main__":
    main()