#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Milthm story & raingpt updater
放在 story/ 目录下，根据相对路径自动从 milthm_unpack / milthm-archive 获取最新资源，
重新生成 vitepress 文档并编译。

相对路径（相对于本文件所在目录 story/）：
  ../milthm_unpack/Assets/TextAsset              -> 剧情 .bytes
  ../milthm_unpack/Assets/Resources/localization -> 多语言 json + story.txt
  ../milthm_unpack/Assets/Resources/tips         -> raingpt tips
  ../milthm_unpack/Assets/Resources/raingpt      -> raingpt 图片
  ../milthm_unpack/Assets/Texture2D              -> me.png / raingpt.png
  ../milthm-archive/code/unified.py              -> bytes 解压（备用，实际用 zstandard 直接解压，与 unified.py 同逻辑）

使用：
  python3 update.py              # 完整更新 + 编译
  python3 update.py --no-build   # 仅更新 md，不编译
"""
import os
import re
import sys
import json
import glob
import shutil
import subprocess
import html as htmlmod
from pathlib import Path
import yaml

# ---------- 路径 ----------
HERE = Path(__file__).resolve().parent
CK = HERE.parent
TEXTASSET = CK / "milthm_unpack/Assets/TextAsset"
LOCALIZATION = CK / "milthm_unpack/Assets/Resources/localization"
TIPS_DIR = CK / "milthm_unpack/Assets/Resources/tips"
TIPS_RES = TIPS_DIR / "resources"
RAINGPT_IMG_SRC = CK / "milthm_unpack/Assets/Resources/raingpt"
TEXTURE2D = CK / "milthm_unpack/Assets/Texture2D"
UNIFIED_PY = CK / "milthm-archive/code/unified.py"

DOCS = HERE / "vitepress/docs"
STORY_DOCS = DOCS / "milthm/story"
RAINGPT_DOCS = DOCS / "milthm/raingpt"
RAINGPT_FILES_DST = RAINGPT_DOCS / "files"
FILES_RAINGPT_DST = HERE / "files/raingpt"
CONFIG_JS = DOCS / ".vitepress/config.js"

LANGS = ["zh_Hans","zh_Hant","yue_Hant","en","ja","es","fr","ko","ru","vi"]

# ---------- 工具 ----------
def load_json_with_fallback(path, fallback_path=None):
    try:
        d=json.load(open(path,encoding="utf-8"))
    except:
        d={}
    if fallback_path and fallback_path.exists():
        fb=json.load(open(fallback_path,encoding="utf-8"))
        for k,v in fb.items():
            if k not in d or not d[k]:
                d[k]=v
    return d

# 来自 milthm-archive/code/story/1.py 的文本处理
def process_text_story(text):
    if not text:
        return ""
    # 与 1.py 的 process_text 保持一致：保留 html 标签，双换行
    # 简化：直接按 1.py 逻辑
    import re as _re
    lines = text.split('\n')
    processed_lines=[]
    for line in lines:
        if _re.search(r'<[^>]+>', line):
            processed_lines.append(line)
        else:
            s=line.strip()
            processed_lines.append(s if s else "")
    # 重建，换行翻倍
    result=[]
    i=0
    while i < len(processed_lines):
        cur=processed_lines[i]
        if cur:
            if _re.search(r'<[^>]+>', cur):
                block=[cur]; i+=1
                while i < len(processed_lines):
                    nxt=processed_lines[i]
                    if _re.search(r'<[^>]+>', nxt) or not nxt:
                        block.append(nxt); i+=1
                    else:
                        break
                doubled=[]
                for lb in block:
                    doubled.append(lb)
                    if not lb:
                        doubled.append("")
                result.append('\n'.join(doubled))
            else:
                result.append(cur); i+=1
        else:
            empt=[cur]; i+=1
            while i < len(processed_lines) and not processed_lines[i]:
                empt.append(processed_lines[i]); i+=1
            doubled=[]
            for e in empt:
                doubled.append(e); doubled.append("")
            result.append('\n'.join(doubled))
    final_lines=[]
    for item in result:
        for line in item.split('\n'):
            final_lines.append(line)
    final_result=[]
    for idx, line in enumerate(final_lines):
        final_result.append(line)
        if idx < len(final_lines)-1:
            final_result.append("")
    return '<br />'.join(final_result)

def preserve_html_formatting(text):
    text = re.sub(r'<color=([^>]+)>', r'<span style="color:\1">', text)
    text = re.sub(r'</color>', r'</span>', text)
    text = re.sub(r'<size=([^>]+)>', r'<span style="font-size:\1">', text)
    text = re.sub(r'</size>', r'</span>', text)
    return text

def process_story_text(text):
    if not text:
        return ""
    # 与 1.py 一致
    v=process_text_story(text)
    v=preserve_html_formatting(v)
    return v

# raingpt 的 process_text（来自 archive 1.py 的完整版，含 rotate/voffset）
def process_raingpt_text(text):
    # <size>
    text = re.sub(r"<size=(\d+)>(.*?)</size>", lambda m: f'<span style="font-size:{m.group(1)}px">{m.group(2)}</span>', text, flags=re.DOTALL)
    # <color>
    text = re.sub(r"<color=([#a-zA-Z0-9]+)>(.*?)</color>", lambda m: f'<span style="color:{m.group(1)}">{m.group(2)}</span>', text, flags=re.DOTALL)
    # <b>
    text = re.sub(r"<b>(.*?)</b>", lambda m: f"<strong>{m.group(1)}</strong>", text, flags=re.DOTALL)
    # <rotate>
    def rotate_each(inner, deg_str):
        deg=float(deg_str)
        parts=re.split(r"(<[^>]+>)", inner)
        out=[]
        for p in parts:
            if not p: continue
            if p.startswith("<") and p.endswith(">"):
                out.append(p); continue
            for ch in p:
                if ch==" ": ch="&nbsp;"
                out.append(f'<span style="display:inline-block;transform:rotate({deg}deg)">{ch}</span>')
        return "".join(out)
    text = re.sub(r'<rotate\s*=\s*"?(-?\d+(?:\.\d+)?)"?\s*>(.*?)</rotate\s*>', lambda m: rotate_each(m.group(2), m.group(1)), text, flags=re.DOTALL|re.IGNORECASE)
    # <voffset> 状态
    def apply_voffset(t):
        pat=re.compile(r'<voffset\s*=\s*([-]?\d*\.?\d+)\s*(em|px)\s*>', re.I)
        pos=0; cur=None; out=[]
        for mm in pat.finditer(t):
            s,e=mm.span()
            seg=t[pos:s]
            if seg:
                # wrap
                if cur is None:
                    out.append(seg)
                else:
                    val=float(re.match(r'([-]?\d*\.?\d+)', cur).group(1)); unit=re.search(r'(em|px)', cur).group(1); inv=f"{-val}{unit}"
                    parts=re.split(r"(<[^>]+>)", seg)
                    rr=[]
                    for p in parts:
                        if not p: continue
                        if p.startswith("<") and p.endswith(">"): rr.append(p)
                        else: rr.append(f'<span style="position:relative;top:{inv}">{p}</span>')
                    out.append("".join(rr))
            cur=f"{mm.group(1)}{mm.group(2)}"; pos=e
        tail=t[pos:]
        if tail:
            if cur is None:
                out.append(tail)
            else:
                val=float(re.match(r'([-]?\d*\.?\d+)', cur).group(1)); unit=re.search(r'(em|px)', cur).group(1); inv=f"{-val}{unit}"
                parts=re.split(r"(<[^>]+>)", tail)
                rr=[]
                for p in parts:
                    if not p: continue
                    if p.startswith("<") and p.endswith(">"): rr.append(p)
                    else: rr.append(f'<span style="position:relative;top:{inv}">{p}</span>')
                out.append("".join(rr))
        return "".join(out)
    text=apply_voffset(text)
    text=re.sub(r"[\u0300-\u036F]+","", text)
    text=text.replace("\n","<br>")
    # fix unclosed tags
    text=re.sub(r"<color=([#a-zA-Z0-9]+)><b>(.+?)(?=</|$)", lambda m: f'<span style="color:{m.group(1)}"><strong>{m.group(2)}</strong></span>', text)
    text=re.sub(r"<color=([#a-zA-Z0-9]+)>(.+?)(?=</|$)", lambda m: f'<span style="color:{m.group(1)}">{m.group(2)}</span>', text)
    text=re.sub(r"<b>(.+?)(?=</|$)", lambda m: f"<strong>{m.group(1)}</strong>", text)
    # escape unknown tags
    tag_pat=r"<(span|strong|img|br)(?:\s+[^>]*?)?/?>|</(span|strong)>"
    ph="__TAG_TEMP__"; tags=[]
    def save(m):
        tags.append(m.group(0)); return f"{ph}{len(tags)-1}__"
    tmp=re.sub(tag_pat, save, text, flags=re.I)
    tmp=tmp.replace("<","&lt;").replace(">","&gt;")
    for i,tg in enumerate(tags):
        tmp=tmp.replace(f"{ph}{i}__", tg)
    return tmp

def get_avatar(sender):
    s=sender.strip().lower()
    if s in ("me","raingpt"):
        return f"/story/files/raingpt/{s}.png"
    return f"/story/files/raingpt/avatar_{s}.png"

# ---------- 解压 bytes ----------
def decode_story_bytes():
    """解压 TextAsset/main_story_*.bytes -> {name: text}，优先用 zstandard（与 unified.py 同逻辑）"""
    try:
        import zstandard as zstd
        has_zstd=True
    except:
        has_zstd=False
    out={}
    for p in TEXTASSET.glob("main_story_*.bytes"):
        raw=p.read_bytes()
        txt=None
        if has_zstd:
            try:
                txt=zstd.ZstdDecompressor().decompress(raw).decode("utf-8")
            except:
                pass
        if txt is None:
            # 尝试 unified.py 的逻辑（若可用）
            try:
                import importlib.util
                spec=importlib.util.spec_from_file_location("unified", str(UNIFIED_PY))
                if spec and spec.loader:
                    mod=importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    # unified 有 classify / process 逻辑，这里简化：直接尝试 utf-8
                    txt=raw.decode("utf-8")
            except:
                pass
        if txt is None:
            try:
                txt=raw.decode("utf-8")
            except:
                continue
        # 简单校验：包含 ##story:
        if "##story:" in txt:
            out[p.stem]=txt
    # 额外：main_story_1_ed_1 等
    return out

# ---------- 解析 AVG 剧本 ----------
def parse_avg_blocks(script_text):
    """
    解析 AVG 剧本为 blocks：
      ('text', [say_id, ...])
      ('choice', opts=[id,...], branches={id:[say_id,...]}, order=[id,...])
    分支缩进由 StoryChoice 组件处理，默认选中第一个。
    忽略 ##if/##mark 等状态指令，仅收集 say。
    """
    lines=script_text.splitlines()
    blocks=[]
    text_buf=[]
    pending=None  # {opts:[], branches:{}, cur:None, order:[]}
    i=0
    while i < len(lines):
        raw=lines[i]; s=raw.strip()
        if not s or s.startswith("//"):
            i+=1; continue
        if s.startswith("##story:") or s.startswith("##non-block") or s.startswith("##end_non-block"):
            i+=1; continue
        m_say=re.match(r'^##say2?:.*\|(-?\d+)\s*$', s)
        if m_say:
            sid=m_say.group(1)
            if pending is not None and pending.get("cur") is not None:
                pending["branches"][pending["cur"]].append(sid)
            else:
                text_buf.append(sid)
            i+=1; continue
        if s.startswith("##question:"):
            # flush text
            if text_buf:
                blocks.append(("text", list(text_buf)))
                text_buf=[]
            # flush previous pending choice if any
            if pending is not None and pending.get("opts"):
                # 完成上一个 choice（若还在 pending 且有分支）
                blocks.append(("choice", pending))
            pending={"opts":[], "branches":{}, "cur":None, "order":[]}
            i+=1; continue
        if s.startswith("|"):
            if pending is not None:
                opt=s[1:].strip()
                pending["opts"].append(opt)
                pending["order"].append(opt)
                if opt not in pending["branches"]:
                    pending["branches"][opt]=[]
            i+=1; continue
        if s.startswith("##choice:"):
            # ##choice:ID 或 ##choice:ID|cond
            cid=s[len("##choice:"):].split("|")[0].strip()
            if pending is not None:
                pending["cur"]=cid
                if cid not in pending["branches"]:
                    pending["branches"][cid]=[]
                    if cid not in pending["order"]:
                        pending["order"].append(cid)
            else:
                # 孤立的 choice（理论上不应出现，视为新 choice）
                pending={"opts":[cid], "branches":{cid:[]}, "cur":cid, "order":[cid]}
            i+=1; continue
        if s.startswith("##end_choice"):
            if pending is not None:
                pending["cur"]=None
                # 预判下一个是否为 choice，若不是则 choice 结束，继续收集 text
                # 实际上多个 choice 连续属于同一 question；下一个若不是 choice 则 choice 块结束
                # 偷看下一行
                nxt = lines[i+1].strip() if i+1 < len(lines) else ""
                if not nxt.startswith("##choice:"):
                    # choice 块结束，落盘
                    # 仅当 opts 非空才视为有效 choice；否则丢弃
                    if pending["opts"] or pending["order"]:
                        # 若 opts 为空但有 branches，用 order
                        if not pending["opts"]:
                            pending["opts"]=list(pending["order"])
                        blocks.append(("choice", pending))
                    pending=None
            i+=1; continue
        if s.startswith("##if") or s.startswith("##else") or s.startswith("##endif") or s.startswith("##mark:"):
            i+=1; continue
        # 其他指令（scene/chara/bgm 等）忽略
        i+=1
    if text_buf:
        blocks.append(("text", list(text_buf)))
    if pending is not None and (pending.get("opts") or pending.get("order")):
        # 兜底：若 opts 为空用 order
        if not pending["opts"]:
            pending["opts"]=list(pending["order"])
        blocks.append(("choice", pending))
    return blocks

# ---------- 生成 story md ----------
def gen_story_md():
    print("== 生成 story ==")
    scripts=decode_story_bytes()
    print(f"  解压 {len(scripts)} 个 AVG 剧本")
    # 读取 story.txt 结构（仅用于标题校验，实际按模板硬编码章节顺序，保持与现站一致）
    # 为多语言标题准备：加载所有 json
    lang_data={}
    en_data=load_json_with_fallback(LOCALIZATION/"en.json")
    for lang in LANGS:
        p=LOCALIZATION/f"{lang}.json"
        if p.exists():
            lang_data[lang]=load_json_with_fallback(p, LOCALIZATION/"en.json")
        else:
            lang_data[lang]=dict(en_data)

    # 章节标题 key 映射（与模板 1.md 一致，修正 Chapter2 -> MainStory2）
    def title_for(lang, key, fallback=""):
        d=lang_data.get(lang,{})
        v=d.get(key,"")
        if not v or not str(v).strip():
            v=en_data.get(key,"") or fallback
        return str(v).strip() if v else fallback

    for lang in LANGS:
        d=lang_data[lang]
        out_lines=[]
        # 辅助：取标题
        def T(k, fb=""): return title_for(lang, k, fb)
        # 辅助：取 say 文本
        def say_text(ep, sid):
            key=f"{ep}.say{sid}"
            v=d.get(key)
            if v is None or (isinstance(v,str) and not v.strip()):
                v=en_data.get(key,"")
            if v is None:
                return ""
            return process_story_text(str(v))
        def choice_text(ep, cid):
            key=f"{ep}.choice{cid}"
            v=d.get(key)
            if v is None or (isinstance(v,str) and not v.strip()):
                v=en_data.get(key,"") or cid
            return process_story_text(str(v)).replace("<br />"," ").strip()

        # --- 主线 ---
        out_lines.append(f"## {T('story.main.title','主线故事')} <a id=\"story\"></a>")
        out_lines.append("")
        out_lines.append(f"### {T('noun.chapter.main_0.subtitle','序章')}: {T('noun.chapter.main_0.title','雨的声音')} <a id=\"chapter0\"></a>")
        out_lines.append("")
        for idx in range(1,7):
            key=f"story.main.0.{idx}"
            txt=d.get(key) or en_data.get(key,"")
            out_lines.append(f"#### 0.{idx} <a id=\"chapter0-{idx}\"></a>")
            out_lines.append("")
            out_lines.append(process_story_text(str(txt)) if txt else "")
            out_lines.append("")
            out_lines.append("---")
            out_lines.append("")
        # chapter1
        out_lines.append(f"### {T('Chapter1.SubTitle','主线章节一')}: {T('Chapter1.Title','甜与苦的一体两面')} <a id=\"chapter1\"></a>")
        out_lines.append("")
        for n in range(1,8):
            ep=f"main_story_1_{n}"
            script=scripts.get(ep,"")
            out_lines.append(f"#### 1.{n} <a id=\"chapter1-{n}\"></a>")
            out_lines.append("")
            if script:
                blocks=parse_avg_blocks(script)
                for kind, *rest in blocks:
                    if kind=="text":
                        sids=rest[0]
                        for sid in sids:
                            t=say_text(ep, sid)
                            if t:
                                # 保留 <br /> 但作为列表项
                                out_lines.append(f"- {t}")
                        out_lines.append("")
                    elif kind=="choice":
                        info=rest[0]
                        opts=info.get("opts") or info.get("order") or []
                        branches=info.get("branches",{})
                        order=info.get("order") or opts
                        # 选项文本
                        opt_labels=[choice_text(ep, o) or o for o in order]
                        # 若分支为空则跳过
                        if not opt_labels:
                            continue
                        # 生成 StoryChoice
                        # 用单引号包裹 JSON，避免与内容双引号冲突；转义单引号
                        import json as _json
                        opts_json=_json.dumps(opt_labels, ensure_ascii=False)
                        # 支分支：每个分支的 say 列表 -> html 列表
                        # 为避免 JSON 单引号问题，转义 '
                        def esc(s): return s.replace("'","&#39;")
                        # 构造组件
                        out_lines.append(f"<StoryChoice :options='{esc(opts_json)}'>")
                        out_lines.append("")
                        for bi, cid in enumerate(order):
                            sids=branches.get(cid,[])
                            out_lines.append(f"<template #branch-{bi}>")
                            out_lines.append("")
                            for sid in sids:
                                t=say_text(ep, sid)
                                if t:
                                    out_lines.append(f"- {t}")
                            if not sids:
                                out_lines.append(f"<!-- 空分支 {cid} -->")
                            out_lines.append("")
                            out_lines.append("</template>")
                            out_lines.append("")
                        out_lines.append("</StoryChoice>")
                        out_lines.append("")
                    else:
                        pass
            else:
                # 无脚本则跳过
                pass
            out_lines.append("---")
            out_lines.append("")
        # 尾声 + 露薇娅 + 苏珊
        out_lines.append(f"#### 尾声 <a id=\"chapter1-ed\"></a>")
        out_lines.append("")
        ep="main_story_1_ed_1"
        script=scripts.get(ep,"")
        if script:
            blocks=parse_avg_blocks(script)
            for kind, *rest in blocks:
                if kind=="text":
                    for sid in rest[0]:
                        t=say_text(ep,sid)
                        if t: out_lines.append(f"- {t}")
                    out_lines.append("")
                elif kind=="choice":
                    info=rest[0]; opts=info.get("order") or info.get("opts") or []
                    branches=info.get("branches",{})
                    opt_labels=[choice_text(ep,o) or o for o in opts]
                    if opt_labels:
                        import json as _json
                        opts_json=_json.dumps(opt_labels, ensure_ascii=False).replace("'","&#39;")
                        out_lines.append(f"<StoryChoice :options='{opts_json}'>")
                        out_lines.append("")
                        for bi,cid in enumerate(opts):
                            for sid in branches.get(cid,[]):
                                t=say_text(ep,sid)
                                if t:
                                    # 需在对应分支模板内
                                    pass
                            # 简化：直接展开
                        # 为简化，复用通用渲染：每个分支单独模板
                        for bi,cid in enumerate(opts):
                            out_lines.append(f"<template #branch-{bi}>")
                            out_lines.append("")
                            for sid in branches.get(cid,[]):
                                t=say_text(ep,sid)
                                if t: out_lines.append(f"- {t}")
                            out_lines.append("")
                            out_lines.append("</template>")
                            out_lines.append("")
                        out_lines.append("</StoryChoice>")
                        out_lines.append("")
        else:
            out_lines.append("")
        out_lines.append("---")
        out_lines.append("")
        # 露薇娅 / 苏珊（段落，非列表）
        for cid_key, anchor, fallback_name in [("character.milthm.luvia","chapter1-luvia","露薇娅"),("character.milthm.susan","chapter1-susan","苏珊")]:
            name=T(cid_key, fallback_name)
            out_lines.append(f"#### {name} <a id=\"{anchor}\"></a>")
            out_lines.append("")
            # 对应段落 key：story.main.1.epilogue.luvia / susan
            ep_key="story.main.1.epilogue.luvia" if "luvia" in cid_key else "story.main.1.epilogue.susan"
            txt=d.get(ep_key) or en_data.get(ep_key,"")
            out_lines.append(process_story_text(str(txt)) if txt else "")
            out_lines.append("")
            out_lines.append("---")
            out_lines.append("")
        # chapter2
        out_lines.append(f"### {T('MainStory2.SubTitle','主线章节二')}: {T('MainStory2.Title','因你而存在的理想国')} <a id=\"chapter2\"></a>")
        out_lines.append("")
        for n in range(1,13):
            ep=f"main_story_2_{n}"
            script=scripts.get(ep,"")
            out_lines.append(f"#### 2.{n} <a id=\"chapter2-{n}\"></a>")
            out_lines.append("")
            if script:
                blocks=parse_avg_blocks(script)
                for kind, *rest in blocks:
                    if kind=="text":
                        for sid in rest[0]:
                            t=say_text(ep,sid)
                            if t: out_lines.append(f"- {t}")
                        if rest[0]:
                            out_lines.append("")
                    elif kind=="choice":
                        info=rest[0]
                        order=info.get("order") or info.get("opts") or []
                        branches=info.get("branches",{})
                        # opts 来自 order
                        opt_labels=[choice_text(ep,o) or o for o in order]
                        # 过滤空
                        if not opt_labels:
                            continue
                        import json as _json
                        opts_json=_json.dumps(opt_labels, ensure_ascii=False).replace("'","&#39;")
                        out_lines.append(f"<StoryChoice :options='{opts_json}'>")
                        out_lines.append("")
                        for bi,cid in enumerate(order):
                            sids=branches.get(cid,[])
                            out_lines.append(f"<template #branch-{bi}>")
                            out_lines.append("")
                            for sid in sids:
                                t=say_text(ep,sid)
                                if t: out_lines.append(f"- {t}")
                            if not sids:
                                out_lines.append(f"<!-- 空分支 {cid} -->")
                            out_lines.append("")
                            out_lines.append("</template>")
                            out_lines.append("")
                        out_lines.append("</StoryChoice>")
                        out_lines.append("")
            else:
                # 无脚本，尝试直接用 json 的 say 键顺序
                keys=[k for k in d if k.startswith(ep+".say")]
                # 按数字排序
                def num(k):
                    try: return int(re.search(r'say(-?\d+)',k).group(1))
                    except: return 0
                for k in sorted(keys, key=num):
                    t=process_story_text(str(d[k]))
                    if t: out_lines.append(f"- {t}")
                out_lines.append("")
            out_lines.append("---")
            out_lines.append("")
        # 支线
        out_lines.append(f"## {T('story.side.title','支线故事')} <a id=\"side\"></a>")
        out_lines.append("")
        out_lines.append(f"### {T('SideStory1.Title','花裳随雨得春迟')} <a id=\"side1\"></a>")
        out_lines.append("")
        for idx in range(1,7):
            key=f"story.side.1.{idx}"
            txt=d.get(key) or en_data.get(key,"")
            out_lines.append(f"#### 1.{idx}  <a id=\"side1-{idx}\"></a>")
            out_lines.append("")
            out_lines.append(process_story_text(str(txt)) if txt else "")
            out_lines.append("")
            out_lines.append("---")
            out_lines.append("")
        # 联动
        out_lines.append(f"## {T('Collaboration.Title','联动')} <a id=\"Collaboration\"></a>")
        out_lines.append("")
        out_lines.append(f"### {T('RainWorld.Title','雨世界')} <a id=\"rainworld\"></a>")
        out_lines.append("")
        for key, aid in [("story.rainworld.0.1","rainworld0-1"),("story.rainworld.0.2","rainworld0-2"),("story.rainworld.0.3","rainworld0-3"),
                         ("story.rainworld.1.1","rainworld1-1"),("story.rainworld.1.2","rainworld1-2"),("story.rainworld.1.3","rainworld1-3"),
                         ("story.rainworld.2.1","rainworld2-1"),("story.rainworld.2.2","rainworld2-2"),("story.rainworld.2.3","rainworld2-3"),
                         ("story.rainworld.3.1","rainworld3-1")]:
            txt=d.get(key) or en_data.get(key,"")
            out_lines.append(f"#### {key.split('.')[-1].replace('0.','0.')}  <a id=\"{aid}\"></a>" if False else f"#### {key.split('.')[-1]}  <a id=\"{aid}\"></a>")
            # 简化：直接按模板锚点
            # 为保持与现站一致，使用硬编码锚点
            out_lines.append("")
            out_lines.append(process_story_text(str(txt)) if txt else "")
            out_lines.append("")
            out_lines.append("---")
            out_lines.append("")
        # rainworld2 & notanote 用模板锚点
        for key, aid, title in [("story.rainworld2.superstructure_x","rainworld-superstructure-x","superstructure x"),
                                ("story.rainworld2.journey_bridge","rainworld-journey-bridge","journey bridge"),
                                ("story.rainworld2.journey_shoreline","rainworld-journey-shoreline","journey shoreline"),
                                ("story.rainworld2.journey_industrial_complex","rainworld-journey-industrial-complex","journey industrial complex"),
                                ("story.rainworld2.journey_downpour","rainworld-journey-downpour","journey downpour"),
                                ("story.rainworld2.journey_sky_islands","rainworld-journey-sky-islands","journey sky islands"),
                                ("story.rainworld2.journey_seven_red_suns","rainworld-journey-seven-red-suns","journey seven red suns"),
                                ("story.rainworld2.journey_deactivated_monsoon","rainworld-journey-deactivated-monsoon","journey deactivated monsoon"),
                                ("story.rainworld2.archived_file","rainworld-archived-file","archived file")]:
            txt=d.get(key) or en_data.get(key,"")
            out_lines.append(f"#### {title}  <a id=\"{aid}\"></a>")
            out_lines.append("")
            out_lines.append(process_story_text(str(txt)) if txt else "")
            out_lines.append("")
            out_lines.append("---")
            out_lines.append("")
        out_lines.append(f"### Notanote")
        out_lines.append("")
        for idx in range(1,6):
            key=f"story.notanote.{idx}"
            txt=d.get(key) or en_data.get(key,"")
            out_lines.append(f"#### {idx}  <a id=\"notanote-{idx}\"></a>")
            out_lines.append("")
            out_lines.append(process_story_text(str(txt)) if txt else "")
            out_lines.append("")
            out_lines.append("---")
            out_lines.append("")
        # 修正 rainworld 锚点（与现站保持一致，使用 hardcode）
        content="\n".join(out_lines)
        # 修正 0.1/1.1 等显示
        # 写入
        STORY_DOCS.mkdir(parents=True, exist_ok=True)
        (STORY_DOCS/f"{lang}.md").write_text(content, encoding="utf-8")
        print(f"  -> {lang}.md ({len(content)} 字符)")

# ---------- raingpt ----------
def gen_raingpt():
    print("== 生成 raingpt ==")
    RAINGPT_DOCS.mkdir(parents=True, exist_ok=True)
    RAINGPT_FILES_DST.mkdir(parents=True, exist_ok=True)
    FILES_RAINGPT_DST.mkdir(parents=True, exist_ok=True)
    cfg_path=TIPS_DIR/"config_zh-cn.txt"
    if not cfg_path.exists():
        print("  ! 未找到", cfg_path)
        return
    cfg=yaml.safe_load(open(cfg_path,encoding="utf-8"))
    tips=cfg.get("Tips",[])
    for tip in tips:
        fname=tip.get("File","")
        if not fname: continue
        src=TIPS_RES/f"{fname}_zh-cn.txt"
        if not src.exists():
            # 兼容不带 _zh-cn
            src2=TIPS_RES/f"{fname}.txt"
            if src2.exists(): src=src2
            else:
                print(f"  ! 缺少 {src}")
                continue
        data=yaml.safe_load(open(src,encoding="utf-8"))
        msgs=data.get("Msg",[])
        md_lines=[]
        for m in msgs:
            sender=str(m.get("Sender","")).strip().lower()
            is_img=int(m.get("IsImage",0) or 0)
            content=str(m.get("Content","")).strip()
            if sender=="system":
                md_lines.append(f'<ChatBubble role="system">\n{process_raingpt_text(content)}\n</ChatBubble>')
                md_lines.append("")
                continue
            role="user" if sender=="me" else "bot"
            avatar=get_avatar(sender)
            if is_img==1:
                md_lines.append(f'<ChatBubble role="{role}" avatar="{avatar}">\n<img src="./files/{content}.png" alt="{content}" class="chat-image" />\n</ChatBubble>')
            else:
                md_lines.append(f'<ChatBubble role="{role}" avatar="{avatar}">\n{process_raingpt_text(content)}\n</ChatBubble>')
            md_lines.append("")
        (RAINGPT_DOCS/f"{fname}.md").write_text("\n".join(md_lines), encoding="utf-8")
        print(f"  -> {fname}.md")
    # 复制图片
    copied=0
    for png in RAINGPT_IMG_SRC.glob("*.png"):
        dst=RAINGPT_FILES_DST/png.name
        if not dst.exists() or png.stat().st_size != dst.stat().st_size:
            shutil.copy2(png, dst); copied+=1
        # avatar 用到的也同步到 files/raingpt
        if png.name.startswith("avatar_") or png.name in ("me.png","raingpt.png"):
            dst2=FILES_RAINGPT_DST/png.name
            if not dst2.exists():
                shutil.copy2(png, dst2); copied+=1
    # Texture2D 的 me/raingpt
    for name in ("me.png","raingpt.png"):
        src=TEXTURE2D/name if (TEXTURE2D/name).exists() else RAINGPT_IMG_SRC/name
        if src.exists():
            dst=FILES_RAINGPT_DST/name
            # 保留现有若已存在且一致则跳过
            if not dst.exists() or src.read_bytes()!=dst.read_bytes():
                shutil.copy2(src, dst); copied+=1
    # online-reality 新增图片（ad_*, avatar_die/alive）已在上面复制
    print(f"  图片已同步 ({copied} 个更新)")
    # 更新 config.js 侧边栏
    update_config_sidebar(tips)

def update_config_sidebar(tips):
    if not CONFIG_JS.exists():
        print("  ! 未找到", CONFIG_JS); return
    text=CONFIG_JS.read_text(encoding="utf-8")
    # 生成 raingpt items
    items=[]
    for tip in tips:
        title=tip.get("Title","")
        fname=tip.get("File","")
        imp=int(tip.get("Important",0) or 0)
        fav='<span class="fav">❤</span>' if imp==1 else ''
        # 转义 '
        title_esc=title.replace("'","\\'")
        items.append(f"            {{ text: '{title_esc}{fav}', link: '/milthm/raingpt/{fname}' }},")
    new_block="          {\n            text: 'Raingpt',\n            collapsible: true,\n            collapsed: true,\n            items: [\n" + "\n".join(items) + "\n            ]\n          }"
    # 替换旧块（匹配 text: 'Raingpt' 到对应 items 结束）
    pat=re.compile(r"\{\s*text:\s*'Raingpt'.*?items:\s*\[.*?\]\s*\}", re.DOTALL)
    if pat.search(text):
        text=pat.sub(new_block, text, count=1)
        CONFIG_JS.write_text(text, encoding="utf-8")
        print("  已更新 config.js Raingpt 侧边栏")
    else:
        print("  ! 未匹配到 Raingpt 侧边栏块，请手动检查")

# ---------- 构建 ----------
def do_build():
    print("== 编译 ==")
    # 1) pnpm install 已在 vitepress 完成则跳过
    # 2) pnpm run docs:build
    vp=HERE/"vitepress"
    # 确保 StoryChoice 已注册（若 update.py 单独运行，检查）
    # 直接在 vitepress 目录构建
    env=os.environ.copy()
    # 使用 pnpm
    try:
        subprocess.run(["pnpm","run","docs:build"], cwd=str(vp), check=True)
    except subprocess.CalledProcessError as e:
        print("  构建失败:", e); return False
    dist=vp/"docs/.vitepress/dist"
    if not dist.exists():
        print("  ! 未找到 dist"); return False
    # 1.sh 的行为：删除旧 assets，复制 dist/* 到 story 根
    for p in (HERE/"assets").glob("*"):
        pass
    # 删除旧 assets
    if (HERE/"assets").exists():
        shutil.rmtree(HERE/"assets")
    # 复制 dist 内容到 HERE
    for item in dist.iterdir():
        dst=HERE/item.name
        if dst.exists():
            if dst.is_dir(): shutil.rmtree(dst)
            else: dst.unlink()
        if item.is_dir(): shutil.copytree(item, dst)
        else: shutil.copy2(item, dst)
    print("  已将 dist 复制到 story 根目录")
    return True

def main():
    import argparse
    ap=argparse.ArgumentParser(description="Milthm story & raingpt updater")
    ap.add_argument("--no-build", action="store_true", help="仅更新 md，不编译")
    args=ap.parse_args()
    print(f"story  : {HERE}")
    print(f"  TextAsset : {TEXTASSET} {'✓' if TEXTASSET.exists() else '✗'}")
    print(f"  localization: {LOCALIZATION} {'✓' if LOCALIZATION.exists() else '✗'}")
    print(f"  tips: {TIPS_DIR} {'✓' if TIPS_DIR.exists() else '✗'}")
    print(f"  unified.py: {UNIFIED_PY} {'✓' if UNIFIED_PY.exists() else '✗'}")
    gen_story_md()
    gen_raingpt()
    if not args.no_build:
        do_build()
    print("完成。")

if __name__=="__main__":
    main()
