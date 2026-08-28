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
# VN 静态资源（背景/立绘/音频/剧本 JSON）直接放到 story 根目录的 vn-assets，
# 不经 vitepress 编译/复制，由播放器以 /story/vn-assets/... 直接引用。
VN_PUBLIC = HERE / "vn-assets"
VN_PUBLIC_BG = VN_PUBLIC / "background"
VN_PUBLIC_CHAR = VN_PUBLIC / "character"
VN_PUBLIC_CG = VN_PUBLIC / "cg"
VN_PUBLIC_SCRIPTS = VN_PUBLIC / "scripts"
VN_PUBLIC_AUDIO = VN_PUBLIC / "audio"
VN_AVG_BG_SRC = CK / "milthm_unpack/Assets/Resources/AVG/background"
VN_AVG_CHAR_SRC = CK / "milthm_unpack/Assets/Resources/AVG/character"
VN_AVG_CG_SRC = CK / "milthm_unpack/Assets/Resources/AVG/cg"
VN_TEXTASSET_BG = TEXTASSET  # bg_* 等也在 TextAsset
# 音频源（剧情脚本中的 ##bgm / ##bgs / ##snd 引用的资源）
VN_AUDIO_BGM_SRC = CK / "milthm_unpack/Assets/Resources/bgm"
VN_AUDIO_BGS_SRC = CK / "milthm_unpack/Assets/Resources/bgs"
VN_AUDIO_SND_SRC = CK / "milthm_unpack/Assets/Resources/snd"

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
def cond_label(src):
    """把 ##if/##elseif 条件整理为可直接展示的条件代码（去掉 uuid 等噪音）。"""
    s2=(src or "").strip()
    if not s2: return "条件分支"
    parts=[p.strip() for p in s2.split("|")]
    key=parts[0].strip()
    # 清理 key：保留变量名/编号段，去掉形如 uuid 的段
    segs=[]
    for x in key.split(","):
        x=x.strip()
        if not x: continue
        if re.fullmatch(r"[0-9a-fA-F]+(?:-[0-9a-fA-F]+)+", x):
            continue
        segs.append(x)
    if len(parts) >= 3:
        op=parts[1]; val=parts[2]
        return f"{'.'.join(segs)} {op} {val}"
    return ".".join(segs)

def parse_say_line(raw, for_player):
    """解析一行 ##say:...|ID，返回 {id,speaker}（for_player）或 say id。"""
    m=re.match(r'^##say2?:(.*?)\|(-?\d+)\s*$', raw.strip())
    if not m: return None
    payload=m.group(1); sid=m.group(2)
    speaker=payload.split("|")[0].strip().rstrip("?")
    return {"id":sid,"speaker":speaker} if for_player else sid

def parse_say_lines(buf, for_player):
    """把收集到的整段原始行过滤为 say 列表。"""
    out=[]
    for raw in buf:
        e=parse_say_line(raw, for_player)
        if e is not None:
            out.append(e)
    return out

# ---------- 角色显示名（多语言） ----------
# ##else 分支选项的多语言文案（解析时先留占位符，生成时再替换）
ELSE_SENTINEL = "@@else@@"
ELSE_LABEL = {
    "zh_Hans": "其它情况", "zh_Hant": "其他情況", "yue_Hant": "其他情況",
    "en": "Otherwise", "ja": "その他", "es": "En otro caso",
    "fr": "Autre cas", "ko": "그 외", "ru": "В остальном", "vi": "Trường hợp khác",
}
# speaker 本体 -> localization character.* 键
CHAR_KEY = {
    "lwy": "character.milthm.luvia",
    "solara": "character.milthm.solara",
    "selene": "character.milthm.selene",
    "ss": "character.milthm.susan", "ss2": "character.milthm.susan",
    "rbt": "character.milthm.robert", "honoka": "character.milthm.honoka",
    "npc-aleksei": "character.milthm.npc-aleksei",
    "npc-alina": "character.milthm.npc-alina",
    "npc-sergay": "character.milthm.npc-sergay",
    "npc-zoya": "character.milthm.npc-zoya",
    "w": "character.general.me", "me": "character.general.me",
    "jm": "character.general.resident", "jm1": "character.general.resident",
    "jm2": "character.general.resident", "jm3": "character.general.resident",
}
# 中文兜底名（与 VnPlayer 旧表一致）
NAME_FALLBACK_ZH = {
    "lwy": "露薇娅", "solara": "索莱娜", "selene": "塞勒涅",
    "ss": "苏珊", "ss2": "苏珊", "w": "我",
    "jm": "居民", "jm1": "居民", "jm2": "居民", "jm3": "居民",
    "honoka": "浅仪洸花", "rbt": "罗伯特",
    "npc-aleksei": "阿列克谢", "npc-alina": "阿琳娜",
    "npc-sergay": "瑟尔盖工头", "npc-zoya": "卓娅",
}
NAME_SUB_FALLBACK_ZH = {
    "selene.sister": "被称为姐姐的人", "solara.solara": "被称为索莱娜的人",
    "npc-nameless.canteen-aunt": "食堂阿姨", "npc-nameless.control-room-chief": "控制室负责人",
    "npc-nameless.control-room-chief-not-aleksei": "控制室负责人",
    "npc-nameless.councilor-a": "议员A", "npc-nameless.councilor-b": "议员B",
    "npc-nameless.councilor-c": "议员C", "npc-nameless.councilor-d": "议员D",
    "npc-nameless.doctor": "医生", "npc-nameless.farm-manager": "农场的管理人",
    "npc-nameless.female": "女性", "npc-nameless.maintenance": "维护工人",
    "npc-nameless.male": "男性", "npc-nameless.resident": "居民",
    "npc-nameless.sluice-team-member": "水闸工作小组组员", "npc-nameless.staff": "工作人员",
    "npc-nameless.worker-carrying-tarpaulin": "正在搬运防水布的工人",
    "npc-nameless.worker-laboring": "正在干活的工人", "npc-nameless.worker-on-platform": "站台上的工人",
    "npc-nameless.worker-resting": "正在休息的工人", "npc-nameless.worker-side": "一旁的工人",
    "npc-nameless.worker-smoothing-tarpaulin": "正在铺平防水布的工人",
    "npc-nameless.worker-wiped": "擦完汗的工人", "npc-nameless.worker-wiping": "正在擦汗的工人",
    "npc-nameless.worker-working": "正在工作的工人",
    "npc-alina.nameless": "正在干活的阿姨", "npc-sergay.nameless": "工头", "npc-zoya.nameless": "正在干活的姐姐",
}

def resolve_speaker(sp):
    """speaker -> (base, sub, character.* 键)。返回 base 为 '' 表示旁白/无。"""
    if not sp:
        return "", "", ""
    base_raw, _, sub = sp.partition(",")
    base = (base_raw.split("/")[0]).strip()
    key = CHAR_KEY.get(base)
    if key is None and base.startswith("npc-nameless"):
        key = "character.general.npc-nameless"
    return base, sub, key

def speaker_display_name(sp, d, en):
    """say speaker -> 显示名。优先当前语言 character.*，缺失回退中文，再回退原 key。旁白返回 ''。"""
    base, sub, key = resolve_speaker(sp)
    if not base or base == "pb":
        return ""
    if key:
        if sub:
            alias = f"{key}.alias.{sub}"
            v = (d.get(alias) or en.get(alias) or "")
            if v and str(v).strip():
                return str(v).strip()
        v = (d.get(key) or en.get(key) or "")
        if v and str(v).strip():
            return str(v).strip()
    if sub:
        zh_alias = NAME_SUB_FALLBACK_ZH.get(f"{base}.{sub}")
        if zh_alias:
            return zh_alias
    return NAME_FALLBACK_ZH.get(base, base)

def parse_avg_blocks(script_text, for_player=False):
    """
    解析 AVG 剧本为 blocks：
      ('text', [say_id, ...] 或 [{id,speaker},...] 当 for_player)
      ('choice', opts=[id,...], branches={id:[say_id,...]}, order=[id,...])
      ('scene', value)
      ('chara', value)
    分支缩进由 StoryChoice 组件处理，默认选中第一个。
    忽略 ##if/##mark 等状态指令，仅收集 say。
    for_player=True 时保留 speaker/scene/chara 供播放器使用
    """
    lines=script_text.splitlines()
    blocks=[]
    text_buf=[]  # 存放 {id,speaker} 或 sid
    pending=None  # {opts:[], branches:{}, cur:None, order:[]}
    cond_stack=[]  # 条件分支栈，每项 {stage, buf, start, order, labels, branches, cur, skip}
    i=0
    def _open_cond(cond):
        # 开启一个新条件分支收集
        order=cond.get("order", [])
        nid=f"c{len(order)}"
        order.append(nid)
        cond.setdefault("labels", {})[nid]=cond_label(cond.get("if_cond"))
        cond.setdefault("branches", {})[nid]=[]
        cond["cur"]=nid
    def _next_is_if(idx):
        # 紧跟（跳过空行/注释）的下一段是否又是一条 ##if 条件，用于把相邻条件合并为同一多选项
        j=idx
        while j < len(lines):
            l=lines[j].strip()
            if not l or l.startswith("//"):
                j+=1; continue
            return l.startswith("##if")
        return False
    while i < len(lines):
        raw=lines[i]; s=raw.strip()
        if not s or s.startswith("//"):
            i+=1; continue
        top=cond_stack[-1] if cond_stack else None
        # -- 条件栈内的分界/结束指令（stacked 状态在 buf/choice 阶段处理） --
        if top is not None and top["stage"] in ("buf","choice"):
            if s.startswith("##elseif") or s.startswith("##else"):
                # 关闭当前分支，开启下一分支
                top["branches"][top["cur"]]=parse_say_lines(top["buf"], for_player)
                top["buf"]=[]
                if top["stage"]=="buf":
                    top["stage"]="choice"
                top["if_cond"]=s.split(":",1)[1].strip() if ":" in s else (ELSE_SENTINEL if s.startswith("##else") else "")
                _open_cond(top)
                i+=1; continue
            if s.startswith("##endif"):
                # 结束条件
                if top["stage"]=="choice":
                    top["branches"][top["cur"]]=parse_say_lines(top["buf"], for_player)
                    if _next_is_if(i+1):
                        # 紧跟又一段条件：合并为同一个多选项，等待下一段 ##if 继续收集分支
                        top["buf"]=[]
                        i+=1; continue
                    cond_stack.pop()
                    if text_buf:
                        blocks.append(("text", list(text_buf)))
                        text_buf=[]
                    condchoice={
                        "opts": list(top["order"]),
                        "order": list(top["order"]),
                        "labels": dict(top["labels"]),
                        "branches": {o: top["branches"][o] for o in top["order"]},
                        "cond": True,
                    }
                    if condchoice["order"]:
                        blocks.append(("choice", condchoice))
                else:
                    # 单分支条件
                    if _next_is_if(i+1):
                        # 其后紧跟又一段条件：作为同一多选项的第一个分支继续合并
                        top["branches"][top["cur"]]=parse_say_lines(top["buf"], for_player)
                        top["buf"]=[]
                        top["stage"]="choice"
                        i+=1; continue
                    # 单独单分支：回退为普通解析（默认取该分支）
                    cond_stack.pop()
                    i=top["start"]-1
                i+=1; continue
            if s.startswith("##question") or (s.startswith("##choice:") and top["stage"]=="buf"):
                # 条件分支内含有真正的玩家选择 -> 放弃条件选项，按普通解析处理（取第一分支）
                top["stage"]="transparent"; top["skip"]=False
                i=top["start"]  # 回退到 ##if 之后的首行，普通处理
                continue
            if s.startswith("##mark:"):
                i+=1; continue
        elif top is not None:  # stage transparent / raw：普通解析，仅跳过 elseif/else 分支体
            if s.startswith("##elseif") or s.startswith("##else"):
                top["skip"]=True
                i+=1; continue
            if s.startswith("##endif"):
                cond_stack.pop()
                i+=1; continue
            if top.get("skip"):
                i+=1; continue
        # -- 开启/兜底条件指令 --
        if s.startswith("##if"):
            if pending is not None and pending.get("cur") is not None:
                # 真实选项分支内出现条件：普通解析
                cond_stack.append({"stage":"raw","skip":False})
            elif top is not None and top["stage"]=="choice":
                # 与上一段条件合并：在同一个选项组中新增一个分支
                top["if_cond"]=s.split(":",1)[1].strip() if ":" in s else ""
                _open_cond(top)
            else:
                cond_stack.append({
                    "stage":"buf", "buf":[], "start":i+1,
                    "order":[], "labels":{}, "branches":{},
                    "if_cond": s.split(":",1)[1].strip() if ":" in s else "", "cur":None,
                })
                _open_cond(cond_stack[-1])
            i+=1; continue
        elif s.startswith("##elseif") or s.startswith("##else") or s.startswith("##endif") or s.startswith("##mark:"):
            i+=1; continue  # 无栈的孤立指令
        # -- 条件收集模式下，把 body 记入当前分支 --
        if top is not None and top["stage"] in ("buf","choice"):
            top["buf"].append(raw)
            i+=1; continue
        if s.startswith("##story:") or s.startswith("##non-block") or s.startswith("##end_non-block"):
            i+=1; continue
        # 场景 / 角色 / 音频 / 情感等 供播放器（故事 md 忽略）
        if for_player:
            block=None
            if s.startswith("##scene:"):
                val=s[len("##scene:"):].split("|")[0].strip()
                block=("scene", val)
            elif s.startswith("##chara_settings:"):
                val=s[len("##chara_settings:"):].strip()
                block=("chara_settings", val)
            elif s.startswith("##chara:"):
                val=s.split(":",1)[1].strip() if ":" in s else ""
                block=("chara", val)
            elif s.startswith("##bgm:"):
                block=("bgm", s[len("##bgm:"):].split("|")[0].strip())
            elif s == "##stop_bgm":
                block=("bgm", "stop")
            elif s.startswith("##bgs:"):
                block=("bgs", s[len("##bgs:"):].split("|")[0].strip())
            elif s == "##stop_bgs":
                block=("bgs", "stop")
            elif s.startswith("##volume_bgs:"):
                block=("volume_bgs", s[len("##volume_bgs:"):].strip())
            elif s.startswith("##snd") and len(s)>5 and s[5] in (":","("):
                val=s.split(":",1)[1].strip()
                block=("se", val)
            elif s.startswith("##emotion:"):
                block=("emotion", s[len("##emotion:"):].strip())
            elif s.startswith("##hide_dialog"):
                block=("hide_dialog", "")
            if block is not None:
                # 分支出（##choice:..##end_choice）内的指令不进入主 blocks
                if pending is not None and pending.get("cur") is not None:
                    pass
                else:
                    # flush text
                    if text_buf:
                        blocks.append(("text", list(text_buf)))
                        text_buf=[]
                    blocks.append(block)
                i+=1; continue
        m_say=re.match(r'^##say2?:(.*?)\|(-?\d+)\s*$', s)
        if m_say:
            payload=m_say.group(1)  # speaker 部分
            sid=m_say.group(2)
            # 提取 speaker（取 '|' 前第一段，去掉 emotion）
            # payload 如 "pb" 或 "lwy?|smile" 或 "solara/frown" 或 "npc-nameless,worker-on-platform|frown"
            # 实际 speaker 为 payload 按 '|' 分割的第一段
            # 对于 ##say:solara|surprise|10011 -> payload = solara|surprise -> speaker = solara
            speaker = payload.split("|")[0].strip() if payload else ""
            # 去除 ? 后缀
            speaker = speaker.rstrip("?")
            entry = {"id": sid, "speaker": speaker} if for_player else sid
            if pending is not None and pending.get("cur") is not None:
                pending["branches"][pending["cur"]].append(entry)
            else:
                text_buf.append(entry)
            i+=1; continue
        if s.startswith("##question:"):
            # flush text
            if text_buf:
                blocks.append(("text", list(text_buf)))
                text_buf=[]
            # flush previous pending choice if any
            if pending is not None and pending.get("opts"):
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
            cid=s[len("##choice:"):].split("|")[0].strip()
            if pending is not None:
                pending["cur"]=cid
                if cid not in pending["branches"]:
                    pending["branches"][cid]=[]
                    if cid not in pending["order"]:
                        pending["order"].append(cid)
            else:
                pending={"opts":[cid], "branches":{cid:[]}, "cur":cid, "order":[cid]}
            i+=1; continue
        if s.startswith("##end_choice"):
            if pending is not None:
                pending["cur"]=None
                nxt = lines[i+1].strip() if i+1 < len(lines) else ""
                if not nxt.startswith("##choice:"):
                    if pending["opts"] or pending["order"]:
                        if not pending["opts"]:
                            pending["opts"]=list(pending["order"])
                        blocks.append(("choice", pending))
                    pending=None
            i+=1; continue
        # 其他指令（scene/chara/bgm 等）忽略（已处理 scene/chara）
        i+=1
    if text_buf:
        blocks.append(("text", list(text_buf)))
    if pending is not None and (pending.get("opts") or pending.get("order")):
        if not pending["opts"]:
            pending["opts"]=list(pending["order"])
        blocks.append(("choice", pending))
    return blocks

def convert_audio_to_ogg(src_path: Path, dst_path: Path):
    """把任意格式的游戏音频（Ogg/Vorbis、WAV、MP3）统一转码为 .ogg，目标已存在则跳过。"""
    if dst_path.exists() and dst_path.stat().st_size > 0:
        return
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    head = src_path.read_bytes()[:4] if src_path.exists() else b""
    # 已是 Ogg：直接拷贝（避免无谓转码）
    if head == b"OggS":
        shutil.copy2(src_path, dst_path)
        return
    if shutil.which("ffmpeg") is None:
        print(f"  ! 未找到 ffmpeg，跳过音频 {src_path.name}")
        return
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src_path),
           "-c:a", "libopus", "-b:a", "96k", "-f", "ogg", str(dst_path)]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if not dst_path.exists() or dst_path.stat().st_size == 0:
        print(f"  ! 音频转码失败: {src_path.name}")


def extract_vn_audio():
    """将剧情用 bgm / bgs / snd 音频导出为 vn-assets/audio 下的 ogg。"""
    print("  == 音频 (bgm/bgs/snd) ==")
    targets = [
        (VN_AUDIO_BGM_SRC, VN_PUBLIC_AUDIO / "bgm"),
        (VN_AUDIO_BGS_SRC, VN_PUBLIC_AUDIO / "bgs"),
    ]
    for src_dir, dst_dir in targets:
        if not src_dir.exists():
            continue
        dst_dir.mkdir(parents=True, exist_ok=True)
        for p in src_dir.glob("*.bytes"):
            convert_audio_to_ogg(p, dst_dir / f"{p.stem}.ogg")
    # snd 保留子目录结构（如 snd/avg/xxx -> audio/snd/avg/xxx）
    if VN_AUDIO_SND_SRC.exists():
        for p in VN_AUDIO_SND_SRC.rglob("*.bytes"):
            rel = p.relative_to(VN_AUDIO_SND_SRC).with_suffix(".ogg")
            convert_audio_to_ogg(p, VN_PUBLIC_AUDIO / "snd" / rel)


def bake_character_alpha():
    """将立绘的 color(.avif) 与 alpha(.alpha.avif) 合并为带透明通道的 .webp，
    浏览器可直接显示，不再依赖 CSS mask（旧方案在透明区域显示黑底）。"""
    print("  == 立绘透明烘焙 (avif+alpha -> webp) ==")
    if shutil.which("ffmpeg") is None:
        print("  ! 未找到 ffmpeg，跳过立绘烘焙")
        return
    done = 0
    for char_dir in VN_PUBLIC_CHAR.iterdir():
        if not char_dir.is_dir():
            continue
        for color in char_dir.glob("*.avif"):
            if color.name.endswith(".alpha.avif"):
                continue
            alpha = color.with_name(color.stem + ".alpha.avif")
            if not alpha.exists():
                continue
            webp = color.with_suffix(".webp")
            if webp.exists():
                continue
            tmp_out = Path("/tmp/vn_bake_out.webp")
            cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(color), "-i", str(alpha),
                   "-filter_complex", "[0:v][1:v]alphamerge", "-frames:v", "1",
                   "-c:v", "libwebp", "-lossless", "1", "-q", "85", str(tmp_out)]
            r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if r.returncode == 0 and tmp_out.exists() and tmp_out.stat().st_size > 0:
                shutil.copy2(tmp_out, webp)
                done += 1
                tmp_out.unlink(missing_ok=True)
    if done:
        print(f"  -> 新烘焙 {done} 个立绘 (.webp)")


def extract_vn_assets():
    """用 unified.py 解压 milimg 背景/立绘/CG 到 public/vn-assets"""
    print("== 提取 VN 资源 ==")
    for src, dst in [
        (VN_AVG_BG_SRC, VN_PUBLIC_BG),
        (VN_AVG_CG_SRC, VN_PUBLIC_CG),
        (TEXTASSET, VN_PUBLIC / "textasset"),
    ]:
        if not src.exists():
            continue
        dst.mkdir(parents=True, exist_ok=True)
        # 收集 .bytes
        tmp_src = Path("/tmp/vn_extract_src")
        tmp_out = Path("/tmp/vn_extract_out")
        tmp_src.mkdir(parents=True, exist_ok=True)
        tmp_out.mkdir(parents=True, exist_ok=True)
        for p in src.glob("*.bytes"):
            shutil.copy2(p, tmp_src / p.name)
        # 背景
        if any(tmp_src.glob("*.bytes")):
            try:
                subprocess.run([sys.executable, str(UNIFIED_PY), str(tmp_src), "-o", str(tmp_out)], check=False, stdout=subprocess.DEVNULL)
                for f in tmp_out.glob("*.avif"):
                    shutil.copy2(f, dst / f.name)
                for f in tmp_out.glob("*.alpha.avif"):
                    shutil.copy2(f, dst / f.name)
                # 清理
                for f in tmp_src.glob("*.bytes"):
                    f.unlink()
                for f in tmp_out.glob("*"):
                    f.unlink()
            except Exception as e:
                print(f"  ! 背景解压失败 {src}: {e}")
    # 角色（递归）
    if VN_AVG_CHAR_SRC.exists():
        VN_PUBLIC_CHAR.mkdir(parents=True, exist_ok=True)
        for char_dir in VN_AVG_CHAR_SRC.iterdir():
            if not char_dir.is_dir():
                continue
            dst_char = VN_PUBLIC_CHAR / char_dir.name
            dst_char.mkdir(parents=True, exist_ok=True)
            tmp_src = Path("/tmp/vn_char_src")
            tmp_out = Path("/tmp/vn_char_out")
            tmp_src.mkdir(parents=True, exist_ok=True)
            tmp_out.mkdir(parents=True, exist_ok=True)
            for p in char_dir.glob("*.bytes"):
                shutil.copy2(p, tmp_src / p.name)
            if any(tmp_src.glob("*.bytes")):
                try:
                    subprocess.run([sys.executable, str(UNIFIED_PY), str(tmp_src), "-o", str(tmp_out)], check=False, stdout=subprocess.DEVNULL)
                    for f in tmp_out.glob("*.avif*"):
                        shutil.copy2(f, dst_char / f.name)
                    for f in tmp_src.glob("*.bytes"):
                        f.unlink()
                    for f in tmp_out.glob("*"):
                        f.unlink()
                except Exception as e:
                    print(f"  ! 角色 {char_dir.name} 解压失败: {e}")
    # 音频（Ogg 直拷与 MUA 经 unified.py）
    VN_PUBLIC_AUDIO.mkdir(parents=True, exist_ok=True)
    # TextAsset 中的 Ogg（如 rain_heavy 等）直接拷贝
    for p in TEXTASSET.glob("*.bytes"):
        try:
            head = p.read_bytes()[:4]
            if head == b'OggS':
                dst = VN_PUBLIC_AUDIO / (p.stem + ".ogg")
                if not dst.exists():
                    shutil.copy2(p, dst)
        except:
            pass
    # 尝试用 unified.py 解压 TextAsset 中其余 MUA 音频
    tmp_src = Path("/tmp/vn_audio_src")
    tmp_out = Path("/tmp/vn_audio_out")
    tmp_src.mkdir(parents=True, exist_ok=True)
    tmp_out.mkdir(parents=True, exist_ok=True)
    for p in TEXTASSET.glob("*.bytes"):
        # 跳过已处理的 Ogg 与已知非音频
        if p.read_bytes()[:4] == b'OggS':
            continue
        # 仅尝试可能的音频（通过 unified.py 分类）
        shutil.copy2(p, tmp_src / p.name)
    if any(tmp_src.glob("*.bytes")):
        try:
            subprocess.run([sys.executable, str(UNIFIED_PY), str(tmp_src), "-o", str(tmp_out)], check=False, stdout=subprocess.DEVNULL)
            for f in tmp_out.glob("*.ogg"):
                shutil.copy2(f, VN_PUBLIC_AUDIO / f.name)
            for f in tmp_src.glob("*.bytes"):
                f.unlink()
            for f in tmp_out.glob("*"):
                f.unlink()
        except Exception as e:
            print(f"  ! 音频解压失败: {e}")
    # 剧情用的 bgm / bgs / snd
    extract_vn_audio()
    # 立绘透明烘焙
    bake_character_alpha()
    # 清理运行时用不上的资源（更新后即时瘦身，避免堆积）
    prune_vn_assets()

# 与播放器实际 try/catch 路径一一对应的候选 stem，避免误删
def _ref_sets():
    import zstandard as zstd
    bgm, bgs, snd, scenes = set(), set(), set(), set()
    try:
        for p in TEXTASSET.glob("main_story_*.bytes"):
            t = zstd.ZstdDecompressor().decompress(p.read_bytes()).decode("utf-8", "replace")
            for m in re.finditer(r"^##bgm:\s*([^|$\n]+)", t, re.M): bgm.add(m.group(1).strip())
            for m in re.finditer(r"^##bgs:\s*([^|$\n]+)", t, re.M): bgs.add(m.group(1).strip())
            for m in re.finditer(r"^##snd(?:\([^)]*\)\s*:)?[:\s(]*([^\s|)$\n]+)", t, re.M): snd.add(m.group(1).strip())
            for m in re.finditer(r"^##scene:\s*([^|$\n]+)", t, re.M): scenes.add(m.group(1).strip())
    except Exception as e:
        print(f"  ! 资源引用扫描失败: {e}")
    ok = set()
    for n in bgm: ok |= {f"bgm/{n}", f"bgs/{n}", n}
    for n in bgs: ok |= {f"bgs/{n}", f"bgm/{n}", n}
    for n in snd: ok |= {f"snd/{n}", n.split("/")[-1]}
    return ok, scenes, len(bgm) + len(bgs) + len(snd)

def prune_vn_assets():
    print("== 清理未引用 VN 资源 ==")
    ok, scenes, n_refs = _ref_sets()
    # 立绘：avif 源已烘焙为 webp，运行时不需留
    rm = 0
    for f in VN_PUBLIC_CHAR.rglob("*.avif"):
        f.unlink(); rm += 1
    # 背景：仅保留被剧本引用的场景
    for f in VN_PUBLIC_BG.glob("*.avif"):
        if f.stem not in scenes:
            f.unlink(); rm += 1
    # 音频：仅保留播放器候选链会尝试的文件
    for f in VN_PUBLIC_AUDIO.rglob("*.ogg"):
        stem = str(f.relative_to(VN_PUBLIC_AUDIO))[:-4]
        if stem not in ok:
            f.unlink(); rm += 1
    # 运行时无引用的目录整体移除
    for stale in (VN_PUBLIC / "textasset", VN_PUBLIC_CG):
        if stale.is_dir():
            shutil.rmtree(stale); rm += 1
    print(f"  -> 引用 {n_refs} 条音频/场景，清理 {rm} 个文件")

def gen_vn_scripts():
    """为每个 AVG 剧集生成 JSON 供 VnPlayer 使用"""
    print("== 生成 VN 剧本 JSON ==")
    scripts = decode_story_bytes()
    VN_PUBLIC_SCRIPTS.mkdir(parents=True, exist_ok=True)
    # 加载所有语言对话
    all_langs = {}
    for lang in LANGS:
        p = LOCALIZATION / f"{lang}.json"
        if p.exists():
            all_langs[lang] = json.load(open(p, encoding="utf-8"))
        else:
            all_langs[lang] = {}
    # 为每个剧集生成 blocks + dialogues（播放器需要 speaker/scene/chara，故用 for_player=True）
    for ep, script in scripts.items():
        blocks = parse_avg_blocks(script, for_player=True)
        # 收集所有 say/choice id（兼容 dict/sid 两种形式）
        say_ids = set()
        choice_ids = set()
        speakers = set()
        for kind, *rest in blocks:
            if kind == "text":
                for item in rest[0]:
                    sid = item["id"] if isinstance(item, dict) else item
                    say_ids.add(sid)
                    if isinstance(item, dict) and item.get("speaker"):
                        speakers.add(item["speaker"])
            elif kind == "choice":
                info = rest[0]
                for oid in info.get("order", []):
                    choice_ids.add(oid)
                for lst in info.get("branches", {}).values():
                    for it in lst:
                        sid = it["id"] if isinstance(it, dict) else it
                        say_ids.add(sid)
                        if isinstance(it, dict) and it.get("speaker"):
                            speakers.add(it["speaker"])
            elif kind in ("scene","chara"):
                continue
        # 构造 dialogues per lang
        dialogues = {}
        for lang in LANGS:
            d = all_langs.get(lang, {})
            mp = {}
            for sid in say_ids:
                k = f"{ep}.say{sid}"
                v = d.get(k) or all_langs.get("en", {}).get(k) or ""
                mp[f"say{sid}"] = v
            for cid in choice_ids:
                k = f"{ep}.choice{cid}"
                v = d.get(k) or all_langs.get("en", {}).get(k) or ""
                mp[f"choice{cid}"] = v
            # 也包含分支内可能用到的 say（已覆盖）
            dialogues[lang] = mp
        # 将 blocks 转为可序列化结构（保留 speaker/scene/chara）
        serial_blocks = []
        for kind, *rest in blocks:
            if kind == "text":
                # rest[0] 为 [{id,speaker},...]
                serial_blocks.append({"type": "text", "says": rest[0]})
            elif kind == "choice":
                info = rest[0]
                _labels = info.get("labels", {})
                labels_by_lang = {}
                for _lang in LANGS:
                    _lab = {}
                    for _o, _l in _labels.items():
                        _lab[_o] = ELSE_LABEL.get(_lang, "其它情况") if _l == ELSE_SENTINEL else _l
                    labels_by_lang[_lang] = _lab
                serial_blocks.append({
                    "type": "choice",
                    "id": info.get("opts", [None])[0] if info.get("opts") else "",
                    "options": info.get("order", []) or info.get("opts", []),
                    "labels": labels_by_lang,
                    "branches": info.get("branches", {})
                })
            elif kind in ("scene","chara","chara_settings","emotion","bgm","bgs","se","hide_dialog","volume_bgs"):
                serial_blocks.append({"type": kind, "value": rest[0]})
        out = {
            "episode": ep,
            "blocks": serial_blocks,
            "dialogues": dialogues,
            "names": None,
        }
        # 每语言 角色名表 speaker -> 显示名（VnPlayer 用它替代内置中文表）
        names = {}
        all_en = all_langs.get("en", {})
        for lang in LANGS:
            dlang = all_langs.get(lang, {})
            mp = {}
            for sp in sorted(speakers):
                mp[sp] = speaker_display_name(sp, dlang, all_en)
            names[lang] = mp
        out["names"] = names
        # 同时解析 scene/chara 等指令，生成简化 commands 供播放器
        # 解析原始脚本的 scene/chara 等
        commands = []
        for line in script.splitlines():
            s = line.strip()
            if s.startswith("##scene:"):
                commands.append({"cmd": "scene", "arg": s[len("##scene:"):].split("|")[0].strip()})
            elif s.startswith("##chara:"):
                commands.append({"cmd": "chara", "arg": s[len("##chara:"):].strip()})
            elif s.startswith("##chara_settings:"):
                commands.append({"cmd": "chara_settings", "arg": s[len("##chara_settings:"):].strip()})
            elif s.startswith("##say:") or s.startswith("##say2:"):
                # 保留 speaker 和 id 供播放器显示
                # 格式 ##say:speaker|emotion|id 或 ##say:speaker|id
                try:
                    payload = s.split(":", 1)[1]
                    parts = payload.split("|")
                    sid = parts[-1].strip()
                    speaker = parts[0].strip()
                    emotion = parts[1].strip() if len(parts) == 3 else ""
                    commands.append({"cmd": "say", "speaker": speaker, "id": sid, "emotion": emotion})
                except:
                    pass
            elif s.startswith("##question:"):
                qid = s.split("|")[-1].strip() if "|" in s else ""
                commands.append({"cmd": "question", "id": qid})
            elif s.startswith("|"):
                commands.append({"cmd": "option", "id": s[1:].strip()})
            elif s.startswith("##choice:"):
                cid = s[len("##choice:"):].split("|")[0].strip()
                commands.append({"cmd": "choice_start", "id": cid})
            elif s.startswith("##end_choice"):
                commands.append({"cmd": "choice_end"})
            elif s.startswith("##if:"):
                commands.append({"cmd": "if", "cond": s[len("##if:"):].strip()})
            elif s.startswith("##else"):
                commands.append({"cmd": "else"})
            elif s.startswith("##endif"):
                commands.append({"cmd": "endif"})
            elif s.startswith("##mark:"):
                commands.append({"cmd": "mark", "arg": s[len("##mark:"):].strip()})
            elif s.startswith("##hide_dialog"):
                commands.append({"cmd": "hide_dialog"})
            elif s.startswith("##bgm:"):
                commands.append({"cmd": "bgm", "arg": s[len("##bgm:"):].strip()})
            elif s.startswith("##bgs:"):
                commands.append({"cmd": "bgs", "arg": s[len("##bgs:"):].strip()})
        out["commands"] = commands
        (VN_PUBLIC_SCRIPTS / f"{ep}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  -> {ep}.json ({len(serial_blocks)} blocks)")

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
        # 辅助：say 列表 -> 纯文本（- 角色名 + > - 对话 分组）
        def render_says(items, out_lines):
            cur_sp=None
            for it in items:
                sid=it["id"] if isinstance(it, dict) else it
                t=say_text(ep, sid)
                if not t:
                    continue
                sp=it.get("speaker","") if isinstance(it, dict) else ""
                name=speaker_display_name(sp, d, en_data)
                if name:
                    if sp != cur_sp:
                        if out_lines and out_lines[-1] != "":
                            out_lines.append("")
                        out_lines.append(f"- {name}")
                        cur_sp=sp
                    out_lines.append(f"> - {t}")
                else:
                    cur_sp=None
                    out_lines.append(f"- {t}")
            if out_lines and out_lines[-1] != "":
                out_lines.append("")

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
            out_lines.append(f"<VnPlayer episode=\"{ep}\" title=\"1.{n}\" />")
            out_lines.append("")
            if script:
                blocks=parse_avg_blocks(script, for_player=True)
                for kind, *rest in blocks:
                    if kind=="text":
                        render_says(rest[0], out_lines)
                    elif kind=="choice":
                        info=rest[0]
                        opts=info.get("opts") or info.get("order") or []
                        branches=info.get("branches",{})
                        order=info.get("order") or opts
                        labels = {o: (ELSE_LABEL.get(lang, "其它情况") if v == ELSE_SENTINEL else v) for o, v in (info.get("labels") or {}).items()}
                        # 选项文本（条件选择用预设标签，普通选项用 localize）
                        opt_labels=[labels.get(o) or (choice_text(ep, o) or o) for o in order]
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
                            if sids:
                                render_says(sids, out_lines)
                            else:
                                out_lines.append(f"<!-- 空分支 {cid} -->")
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
        out_lines.append(f"<VnPlayer episode=\"main_story_1_ed_1\" title=\"尾声\" />")
        out_lines.append("")
        ep="main_story_1_ed_1"
        script=scripts.get(ep,"")
        if script:
            blocks=parse_avg_blocks(script, for_player=True)
            for kind, *rest in blocks:
                if kind=="text":
                    render_says(rest[0], out_lines)
                elif kind=="choice":
                    info=rest[0]; opts=info.get("order") or info.get("opts") or []
                    branches=info.get("branches",{})
                    labels = {o: (ELSE_LABEL.get(lang, "其它情况") if v == ELSE_SENTINEL else v) for o, v in (info.get("labels") or {}).items()}
                    opt_labels=[labels.get(o) or (choice_text(ep,o) or o) for o in opts]
                    if opt_labels:
                        import json as _json
                        opts_json=_json.dumps(opt_labels, ensure_ascii=False).replace("'","&#39;")
                        out_lines.append(f"<StoryChoice :options='{opts_json}'>")
                        out_lines.append("")
                        for bi,cid in enumerate(opts):
                            out_lines.append(f"<template #branch-{bi}>")
                            out_lines.append("")
                            sids=branches.get(cid,[])
                            if sids:
                                render_says(sids, out_lines)
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
            out_lines.append(f"<VnPlayer episode=\"{ep}\" title=\"2.{n}\" />")
            out_lines.append("")
            if script:
                blocks=parse_avg_blocks(script, for_player=True)
                for kind, *rest in blocks:
                    if kind=="text":
                        render_says(rest[0], out_lines)
                    elif kind=="choice":
                        info=rest[0]
                        order=info.get("order") or info.get("opts") or []
                        branches=info.get("branches",{})
                        labels = {o: (ELSE_LABEL.get(lang, "其它情况") if v == ELSE_SENTINEL else v) for o, v in (info.get("labels") or {}).items()}
                        # opts 来自 order
                        opt_labels=[labels.get(o) or (choice_text(ep,o) or o) for o in order]
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
                            if sids:
                                render_says(sids, out_lines)
                            else:
                                out_lines.append(f"<!-- 空分支 {cid} -->")
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
    # 限制 node 堆内存，防止构建异常膨胀占满内存（常规站点 4G 足够）
    env.setdefault("NODE_OPTIONS", "--max-old-space-size=4096")
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
    try:
        extract_vn_assets()
    except Exception as e:
        print(f"  ! VN 资源提取失败: {e}")
    try:
        gen_vn_scripts()
    except Exception as e:
        print(f"  ! VN 剧本生成失败: {e}")
    gen_raingpt()
    if not args.no_build:
        do_build()
    print("完成。")

if __name__=="__main__":
    main()
