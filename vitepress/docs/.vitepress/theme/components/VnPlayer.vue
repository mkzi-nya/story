<template>
  <span class="vn-trigger-wrapper">
    <button class="vn-play-btn" @click="open = true" :title="`播放 ${title || episode}`">
      <span class="vn-play-icon">▶</span>
      <span>播放</span>
    </button>
    <Teleport to="body" v-if="open">
      <div class="vn-root" @click.self="close" @keydown.esc="close" tabindex="0" ref="rootEl">
        <!-- 全屏舞台 -->
        <div class="vn-stage">
          <!-- 背景层 -->
          <img
            v-if="bgSrc"
            :src="bgSrc"
            class="vn-bg"
            @error="onBgError"
            alt=""
          />
          <div v-else class="vn-bg-fallback"></div>
          <div class="vn-vignette"></div>

          <!-- 角色层 - 透明背景 -->
          <div class="vn-characters">
            <div
              v-for="(ch, idx) in characters"
              :key="idx"
              class="vn-char"
              :style="charPosStyle(idx)"
            >
              <img
                :src="charImgSrc(ch)"
                :alt="ch.name"
                class="vn-char-img"
                :style="charImgStyle(ch)"
                @error="onCharError($event, ch)"
                draggable="false"
              />
            </div>
          </div>

          <!-- 顶部栏 -->
          <div class="vn-topbar">
            <div class="vn-episode-title">{{ title || episode }}</div>
            <div class="vn-top-actions">
              <span class="vn-progress">{{ progressText }}</span>
              <button class="vn-icon-btn" @click="close" aria-label="关闭">✕</button>
            </div>
          </div>

          <!-- 对话 -->
          <transition name="vn-dialog-fade">
            <div
              class="vn-dialog-wrap"
              v-if="currentSay && !showChoices && !finished && !dialogHidden"
              @click="next"
            >
              <div class="vn-dialog">
                <div class="vn-speaker" v-if="speakerName">
                  <span class="vn-speaker-name">{{ speakerName }}</span>
                </div>
                <div class="vn-text" v-html="currentText"></div>
                <div class="vn-next">
                  <span class="vn-next-dot"></span>
                </div>
              </div>
            </div>
          </transition>

          <!-- 点击继续（无对话时 / 对白框隐藏时） -->
          <div
            v-if="(!currentSay || dialogHidden) && !showChoices && !finished"
            class="vn-tap-next"
            @click="next"
          ></div>

          <!-- 选项 -->
          <transition name="vn-choice-fade">
            <div v-if="showChoices" class="vn-choices">
              <div class="vn-choices-inner">
                <p class="vn-choices-hint">请选择</p>
                <button
                  v-for="(opt, idx) in currentChoiceOptions"
                  :key="idx"
                  class="vn-choice-btn"
                  @click="pickChoice(idx)"
                >
                  <span class="vn-choice-index">{{ String.fromCharCode(65 + idx) }}</span>
                  <span class="vn-choice-label">{{ opt.label }}</span>
                </button>
              </div>
            </div>
          </transition>

          <!-- 结束 -->
          <transition name="vn-fade">
            <div v-if="finished" class="vn-finished">
              <div class="vn-finished-card">
                <p class="vn-finished-title">— 本章完 —</p>
                <p class="vn-finished-sub">{{ playingTitle || title || episode }}</p>
                <div class="vn-finished-actions">
                  <button class="vn-btn-primary" @click="restart">重新播放</button>
                  <button v-if="nextSection" class="vn-btn-primary" @click="playNext">播放下一节</button>
                  <button class="vn-btn-ghost" @click="close">退出</button>
                </div>
                <p v-if="chapterEndTip" class="vn-finished-tip">{{ chapterEndTip }}</p>
              </div>
            </div>
          </transition>

          <!-- 音频（隐藏） -->
          <audio ref="bgmAudio" loop preload="auto" @error="onAudioError(bgmAudio)"></audio>
          <audio ref="bgsAudio" loop preload="auto" @error="onAudioError(bgsAudio)"></audio>
          <audio ref="seAudio" preload="auto" @error="onAudioError(seAudio)"></audio>
        </div>
      </div>
    </Teleport>
  </span>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  episode: { type: String, required: true },
  title: { type: String, default: '' },
  lang: { type: String, default: '' }
})

const open = ref(false)
const rootEl = ref(null)
const bgmAudio = ref(null)
const bgsAudio = ref(null)
const seAudio = ref(null)
const bgSrc = ref('')
const characters = ref([])
const currentSay = ref(null)
const showChoices = ref(false)
const currentChoiceOptions = ref([])
const finished = ref(false)
const progressText = ref('')
const dialogHidden = ref(false)

// 章节导航：顺序、标题、章节末自动退出
const EPISODE_ORDER = [
  'main_story_1_1','main_story_1_2','main_story_1_3','main_story_1_4','main_story_1_5',
  'main_story_1_6','main_story_1_7','main_story_1_ed_1',
  'main_story_2_1','main_story_2_2','main_story_2_3','main_story_2_4','main_story_2_5',
  'main_story_2_6','main_story_2_7','main_story_2_8','main_story_2_9','main_story_2_10',
  'main_story_2_11','main_story_2_12'
]
const CHAPTER_ENDS = new Set(['main_story_1_ed_1', 'main_story_2_12'])
const episodeRef = ref(props.episode)
const playingTitle = ref(props.title || shortTitle(props.episode))
const nextSection = computed(() => {
  if (CHAPTER_ENDS.has(episodeRef.value)) return ''
  const idx = EPISODE_ORDER.indexOf(episodeRef.value)
  if (idx < 0 || idx >= EPISODE_ORDER.length - 1) return ''
  return EPISODE_ORDER[idx + 1]
})
const chapterEndTip = computed(() =>
  finished.value && !nextSection.value ? '本节为本章最后一节，即将自动退出…' : ''
)
function shortTitle(ep) {
  if (ep === 'main_story_1_ed_1') return '尾声'
  return ep.replace(/^main_story_/, '').replace('_', '.')
}
let chapterEndTimer = null

let blocks = []
let dialogues = {}
let currentLang = ref('')
let blockIdx = 0
let sayIdx = 0
let prevBgmPlaying = false

function detectLang() {
  if (props.lang) return props.lang
  const path = typeof window !== 'undefined' ? window.location.pathname : ''
  const m = path.match(/\/milthm\/story\/(zh_Hans|zh_Hant|yue_Hant|en|ja|es|fr|ko|ru|vi)/)
  if (m) return m[1]
  return 'zh_Hans'
}

// ---------- 角色文件夹 / 显示名 ----------
const BASE = '/story/'
const folderMap = {}  // ideas: chara_settings 动态更新 id -> 立绘文件夹
const nameMap = {}    // chara_settings 动态更新 id -> 显示名
const emotions = {}   // 每个角色当前表情（##emotion / ##chara:name/expr 更新）
// 缺少 chara_settings 时的默认文件夹
const DEFAULT_FOLDER = {
  lwy: 'luvia-arcadia', jm: 'npc1', jm1: 'npc1', jm2: 'npc1', jm3: 'npc1',
  'npc-aleksei': 'npc1', 'npc-nameless': 'npc1', 'npc-nameless1': 'npc1', 'npc-nameless2': 'npc-female'
}
function folderFor(name) {
  const base = (name || '').split(',')[0].trim()
  if (folderMap[base]) return folderMap[base]
  if (DEFAULT_FOLDER[base]) return DEFAULT_FOLDER[base]
  return base
}
const NAME_TABLE = {
  'lwy': '露薇娅', 'solara': '索莱娜', 'selene': '塞勒涅',
  'ss': '苏珊', 'ss2': '苏珊', 'w': '我',
  'jm': '居民', 'jm1': '居民', 'jm2': '居民', 'jm3': '居民',
  'honoka': '浅仪洸花', 'rbt': '罗伯特',
  'npc-aleksei': '阿列克谢', 'npc-alina': '阿琳娜',
  'npc-sergay': '瑟尔盖工头', 'npc-zoya': '卓娅'
}
const SUB_NAME_TABLE = {
  'pb.broadcast': '广播', 'selene.sister': '被称为姐姐的人', 'solara.solara': '被称为索莱娜的人',
  'npc-nameless.canteen-aunt': '食堂阿姨', 'npc-nameless.control-room-chief': '控制室负责人',
  'npc-nameless.control-room-chief-not-aleksei': '控制室负责人',
  'npc-nameless.councilor-a': '议员A', 'npc-nameless.councilor-b': '议员B',
  'npc-nameless.councilor-c': '议员C', 'npc-nameless.councilor-d': '议员D',
  'npc-nameless.doctor': '医生', 'npc-nameless.farm-manager': '农场的管理人',
  'npc-nameless.female': '女性', 'npc-nameless.maintenance': '维护工人',
  'npc-nameless.male': '男性', 'npc-nameless.resident': '居民',
  'npc-nameless.sluice-team-member': '水闸工作小组组员', 'npc-nameless.staff': '工作人员',
  'npc-nameless.worker-carrying-tarpaulin': '正在搬运防水布的工人',
  'npc-nameless.worker-laboring': '正在干活的工人', 'npc-nameless.worker-on-platform': '站台上的工人',
  'npc-nameless.worker-resting': '正在休息的工人', 'npc-nameless.worker-side': '一旁的工人',
  'npc-nameless.worker-smoothing-tarpaulin': '正在铺平防水布的工人',
  'npc-nameless.worker-wiped': '擦完汗的工人', 'npc-nameless.worker-wiping': '正在擦汗的工人',
  'npc-nameless.worker-working': '正在工作的工人',
  'npc-alina.nameless': '正在干活的阿姨', 'npc-sergay.nameless': '工头', 'npc-zoya.nameless': '正在干活的姐姐'
}

const speakerName = computed(() => {
  if (!currentSay.value) return ''
  const sp = currentSay.value.speaker
  if (!sp || sp === 'pb') return ''
  const [baseRaw, sub] = (sp || '').split(',')
  const base = (baseRaw || '').split('/')[0].trim()
  if (!base) return ''
  if (base === 'pb') return SUB_NAME_TABLE[`pb.${sub}`] || ''
  // 别名（如 npc-nameless1,councilor-a）以显示名（chara_settings 第三段）为基础匹配
  const displayBase = nameMap[base] || base
  if (sub && SUB_NAME_TABLE[`${displayBase}.${sub}`]) return SUB_NAME_TABLE[`${displayBase}.${sub}`]
  if (sub && SUB_NAME_TABLE[`${base}.${sub}`]) return SUB_NAME_TABLE[`${base}.${sub}`]
  return NAME_TABLE[base] || (nameMap[base] ? nameMap[base] : base)
})

const currentText = computed(() => {
  if (!currentSay.value) return ''
  let t = currentSay.value.text || ''
  t = t.replace(/<color=([^>]+)>/g, '<span style="color:$1">').replace(/<\/color>/g, '</span>')
  t = t.replace(/<size=([^>]+)>/g, '<span style="font-size:$1">').replace(/<\/size>/g, '</span>')
  t = t.replace(/<b>/g, '<strong>').replace(/<\/b>/g, '</strong>')
  t = t.replace(/\n/g, '<br>')
  t = t.replace(/<shake[^>]*>/g, '').replace(/<\/shake>/g, '')
  t = t.replace(/<pause[^>]*\/?>/g, ' ')
  t = t.replace(/<voffset[^>]*>/g, '').replace(/<rotate[^>]*>/g, '').replace(/<\/rotate>/g, '')
  return t
})

// 立绘：优先使用烘焙后的透明 .webp；缺失时回退 .avif + alpha mask
const SLOTS = { 1: [50], 2: [32, 68], 3: [22, 50, 78], 4: [15, 38, 62, 85] }
function charImgSrc(ch) {
  const folder = ch.folder || folderFor(ch.name)
  const ext = ch.avif ? 'avif' : 'webp'
  return `${BASE}vn-assets/character/${folder}/${ch.expr}.${ext}`
}
function charAlphaSrc(ch) {
  const folder = ch.folder || folderFor(ch.name)
  return `${BASE}vn-assets/character/${folder}/${ch.expr}.alpha.avif`
}
function alphaMaskStyle(ch) {
  const a = charAlphaSrc(ch)
  return {
    WebkitMaskImage: `url("${a}")`,
    maskImage: `url("${a}")`,
    WebkitMaskSize: 'contain', maskSize: 'contain',
    WebkitMaskRepeat: 'no-repeat', maskRepeat: 'no-repeat',
    WebkitMaskPosition: 'center bottom', maskPosition: 'center bottom'
  }
}
function charImgStyle(ch) {
  return ch.avif ? alphaMaskStyle(ch) : {}
}
function charPosStyle(idx) {
  const n = characters.value.length
  const slots = SLOTS[n] || SLOTS[Math.min(n, 4)]
  const pos = slots[idx] != null ? slots[idx] : 50
  const wide = typeof window === 'undefined' || window.innerWidth >= 800
  let height
  if (!wide) {
    height = n >= 3 ? 'min(52vh, 480px)' : n === 2 ? 'min(60vh, 560px)' : 'min(64vh, 620px)'
  } else if (n >= 4) height = 'min(66vh, 780px)'
  else if (n === 3) height = 'min(72vh, 850px)'
  else if (n === 2) height = 'min(84vh, 1000px)'
  else height = 'min(88vh, 1080px)'
  return { left: pos + '%', height }
}
function onBgError(e) { e.target.style.display = 'none' }
function onCharError(e, ch) {
  if (ch.avif) { e.target.style.display = 'none'; return }
  if (ch.expr !== 'default') { ch.expr = 'default'; return }
  ch.avif = true
}

// 音频控制：禁用文本 bgm，播放 VN 音频
function pauseTextBgm() {
  if (typeof document === 'undefined') return
  prevBgmPlaying = false
  const btn = document.getElementById('bgm-toggle')
  if (btn) prevBgmPlaying = btn.classList.contains('playing')
  // 直接操作全局 audio 对象（MusicToggle 暴露的）
  try {
    if (window.__storyBgm) {
      prevBgmPlaying = !window.__storyBgm.paused || prevBgmPlaying
      window.__storyBgm.pause()
    }
  } catch {}
  window.dispatchEvent(new CustomEvent('vn-bgm-pause'))
  document.querySelectorAll('audio').forEach(a => {
    if (a.src.includes('story.mp3')) {
      prevBgmPlaying = !a.paused || prevBgmPlaying
      try { a.pause() } catch {}
    }
  })
  // 若仍未判定，默认认为需要恢复
  if (prevBgmPlaying === false && btn && btn.classList.contains('playing')) prevBgmPlaying = true
}
function resumeTextBgm() {
  if (typeof document === 'undefined') return
  window.dispatchEvent(new CustomEvent('vn-bgm-resume', { detail: { wasPlaying: prevBgmPlaying } }))
  try {
    if (prevBgmPlaying && window.__storyBgm) {
      window.__storyBgm.play().catch(()=>{})
    }
  } catch {}
  if (!prevBgmPlaying) return
  document.querySelectorAll('audio').forEach(a => {
    if (a.src.includes('story.mp3')) a.play().catch(()=>{})
  })
}
function setAudioSrc(el, paths, volume) {
  if (!el) return
  el._candidates = paths.filter(Boolean)
  el.volume = volume
  loadNextAudio(el)
}
function loadNextAudio(el) {
  if (!el || !el._candidates || !el._candidates.length) return
  const src = el._candidates.shift()
  el.src = src
  const p = el.play()
  if (p && p.catch) p.catch(() => {})
}
function onAudioError(el) {
  loadNextAudio(el)
}
function stopAudio(el) {
  if (!el) return
  el._candidates = []
  el.pause()
  el.currentTime = 0
  el.removeAttribute('src')
}
function playBgm(name) {
  if (!bgmAudio.value) return
  const clean = (name || '').split('|')[0].trim()
  if (!clean || clean === 'none' || clean === 'stop_bgm' || clean === 'stop') {
    stopAudio(bgmAudio.value)
    return
  }
  setAudioSrc(
    bgmAudio.value,
    [`${BASE}vn-assets/audio/bgm/${clean}.ogg`, `${BASE}vn-assets/audio/bgs/${clean}.ogg`, `${BASE}vn-assets/audio/${clean}.ogg`],
    0.6
  )
}
function playBgs(name) {
  if (!bgsAudio.value) return
  const clean = (name || '').split('|')[0].trim()
  if (!clean || clean === 'none' || clean === 'stop_bgs' || clean === 'stop') {
    stopAudio(bgsAudio.value)
    return
  }
  setAudioSrc(
    bgsAudio.value,
    [`${BASE}vn-assets/audio/bgs/${clean}.ogg`, `${BASE}vn-assets/audio/bgm/${clean}.ogg`, `${BASE}vn-assets/audio/${clean}.ogg`],
    0.45
  )
}
function playSe(name) {
  if (!seAudio.value || !name) return
  const clean = name.split('|')[0].trim()
  if (!clean) return
  setAudioSrc(
    seAudio.value,
    [`${BASE}vn-assets/audio/snd/${clean}.ogg`, `${BASE}vn-assets/audio/${clean.split('/').pop()}.ogg`],
    0.7
  )
}

async function loadEpisode() {
  const ep = episodeRef.value
  playingTitle.value = shortTitle(ep)
  currentLang.value = detectLang()
  try {
    const base = (typeof window !== 'undefined' && window.__VP_SITE_DATA__?.base) || '/story/'
    const url = `${base}vn-assets/scripts/${ep}.json`.replace(/\/\//g, '/')
    const fetchUrl = url.startsWith('/story/') ? url : `/story/vn-assets/scripts/${ep}.json`
    const res = await fetch(fetchUrl)
    if (!res.ok) throw new Error(`${fetchUrl} ${res.status}`)
    const data = await res.json()
    blocks = data.blocks || []
    dialogues = data.dialogues || {}
    // 也加载 commands 供音频/场景使用（若存在）
    if (data.commands) {
      // 合并 commands 到 blocks 的便捷：我们已在 blocks 中包含 scene/chara，此处额外处理 bgm/bgs/snd
      // 将 commands 存为全局供 next() 引用
      window.__vn_commands = data.commands
    }
    blockIdx = 0; sayIdx = 0
    characters.value = []; bgSrc.value = ''; finished.value = false
    showChoices.value = false; currentChoiceOptions.value = []
    dialogHidden.value = false
    Object.keys(folderMap).forEach(k => delete folderMap[k])
    Object.keys(nameMap).forEach(k => delete nameMap[k])
    Object.keys(emotions).forEach(k => delete emotions[k])
    pauseTextBgm()
    // 停止之前的 VN 音频
    stopAudio(bgmAudio.value)
    stopAudio(bgsAudio.value)
    stopAudio(seAudio.value)
    if (typeof document !== 'undefined') {
      document.body.style.overflow = 'hidden'
      nextTick(() => rootEl.value?.focus())
    }
    next()
  } catch (e) {
    console.error('VN load failed', e)
    currentSay.value = { speaker: '', id: '', text: `加载失败：${e.message}` }
  }
}

function resolveText(sid) {
  const l = currentLang.value
  return dialogues[l]?.[`say${sid}`] || dialogues[l]?.[`choice${sid}`] || dialogues[l]?.[sid] ||
         dialogues['zh_Hans']?.[`say${sid}`] || dialogues['zh_Hans']?.[`choice${sid}`] || ''
}

function getSayId(item) { return typeof item === 'string' ? item : (item?.id || '') }
function getSpeaker(item) { return typeof item === 'string' ? '' : (item?.speaker || '') }

function next() {
  if (showChoices.value) return
  if (finished.value) return
  while (blockIdx < blocks.length) {
    const blk = blocks[blockIdx]
    if (blk.type === 'text') {
      if (sayIdx < blk.says.length) {
        const item = blk.says[sayIdx]
        const sid = getSayId(item)
        const text = resolveText(sid) || sid
        const speaker = getSpeaker(item)
        currentSay.value = { speaker, id: sid, text }
        sayIdx++
        updateProgress()
        return
      } else {
        blockIdx++; sayIdx = 0; continue
      }
    } else if (blk.type === 'choice') {
      const opts = blk.options || []
      currentChoiceOptions.value = opts.map(oid => ({
        id: oid,
        label: blk.labels?.[oid] || dialogues[currentLang.value]?.[`choice${oid}`] || dialogues['zh_Hans']?.[`choice${oid}`] || dialogues['en']?.[`choice${oid}`] || oid
      }))
      showChoices.value = true
      return
    } else if (blk.type === 'scene') {
      bgSrc.value = `/story/vn-assets/background/${blk.value}.avif`
      blockIdx++; continue
    } else if (blk.type === 'chara') {
      const val = blk.value
      if (!val || val.trim() === '' || val.trim() === 'empty' || val === ':') {
        characters.value = []
      } else {
        const parts = val.split('+').filter(Boolean)
        characters.value = parts.map(p => {
          const seg = p.includes('|') ? p.split('|').pop() : p
          const m = seg.split('/')
          const name = (m[0] || seg).trim()
          let expr = (m[1] || '').trim()
          if (expr) emotions[name] = expr
          else expr = emotions[name] || 'default'
          return { name, folder: folderFor(name), expr }
        }).filter(c => c.name)
      }
      blockIdx++; continue
    } else if (blk.type === 'chara_settings') {
      const parts = (blk.value || '').split('|')
      if (parts[0] && parts[0].trim()) {
        const id = parts[0].trim()
        if (parts[1] && parts[1].trim()) folderMap[id] = parts[1].trim()
        if (parts[2] && parts[2].trim()) nameMap[id] = parts[2].trim()
      }
      blockIdx++; continue
    } else if (blk.type === 'emotion') {
      const [nm, ex] = (blk.value || '').split('|')
      if (nm && ex) {
        emotions[nm.trim()] = ex.trim()
        characters.value = characters.value.map(c =>
          c.name === nm.trim() ? { ...c, expr: ex.trim(), avif: false } : c
        )
      }
      blockIdx++; continue
    } else if (blk.type === 'hide_dialog') {
      // 游戏里 hide_dialog 会在演出转场时收起对话框；web 播放器无转场计时，
      // 若直接隐藏对白框会出现“无可点击目标”而卡住，因此仅作空操作。
      blockIdx++; continue
    } else if (blk.type === 'volume_bgs') {
      const v = parseFloat(blk.value)
      if (!isNaN(v) && bgsAudio.value) bgsAudio.value.volume = Math.min(1, Math.max(0, v))
      blockIdx++; continue
    } else if (blk.type === 'bgm') {
      playBgm(blk.value)
      blockIdx++; continue
    } else if (blk.type === 'bgs') {
      playBgs(blk.value)
      blockIdx++; continue
    } else if (blk.type === 'se' || blk.type === 'snd') {
      playSe(blk.value)
      blockIdx++; continue
    } else {
      blockIdx++; continue
    }
  }
  finished.value = true
  currentSay.value = null
}

function pickChoice(idx) {
  const blk = blocks[blockIdx]
  if (!blk || blk.type !== 'choice') return
  const optId = blk.options[idx]
  showChoices.value = false
  const branchSays = (blk.branches && blk.branches[optId]) || []
  if (branchSays.length) {
    blocks.splice(blockIdx + 1, 0, { type: 'text', says: branchSays })
  }
  blockIdx++
  sayIdx = 0
  next()
}

function close() {
  open.value = false
  finished.value = false
  currentSay.value = null
  showChoices.value = false
  dialogHidden.value = false
  if (chapterEndTimer) { clearTimeout(chapterEndTimer); chapterEndTimer = null }
  stopAudio(bgmAudio.value)
  stopAudio(bgsAudio.value)
  stopAudio(seAudio.value)
  resumeTextBgm()
  exitLandscape()
  if (typeof document !== 'undefined') document.body.style.overflow = ''
}

function restart() { loadEpisode() }

function playNext() {
  if (!nextSection.value) return
  episodeRef.value = nextSection.value
  finished.value = false
  loadEpisode()
}

// 章节末自动退出（下一节为空 = 本章最后一节）
watch(finished, (v) => {
  if (v && !nextSection.value) {
    if (chapterEndTimer) clearTimeout(chapterEndTimer)
    chapterEndTimer = setTimeout(() => { close() }, 3500)
  } else if (!v && chapterEndTimer) {
    clearTimeout(chapterEndTimer)
    chapterEndTimer = null
  }
})

// 手机上播放时自动横屏：进入全屏并尝试锁定横屏
let landscapeLocked = false
function isMobile() {
  if (typeof window === 'undefined') return false
  return (window.matchMedia && window.matchMedia('(pointer: coarse)').matches) || window.innerWidth < 900
}
async function enterLandscape() {
  if (!isMobile() || landscapeLocked) return
  try {
    if (rootEl.value && rootEl.value.requestFullscreen) {
      await rootEl.value.requestFullscreen()
    }
  } catch (e) { /* 全屏被拒绝时忽略 */ }
  try {
    if (window.screen?.orientation?.lock) {
      await window.screen.orientation.lock('landscape')
      landscapeLocked = true
    }
  } catch (e) { /* 部分浏览器不支持锁定 */ }
}
function exitLandscape() {
  if (!landscapeLocked && !document.fullscreenElement) return
  landscapeLocked = false
  try { window.screen?.orientation?.unlock?.() } catch (e) {}
  try {
    if (document.exitFullscreen) document.exitFullscreen()
  } catch (e) {}
}

function updateProgress() {
  const total = blocks.reduce((acc, b) => acc + (b.type === 'text' ? b.says.length : 0), 0)
  const done = blocks.slice(0, blockIdx).reduce((acc, b) => acc + (b.type === 'text' ? b.says.length : 0), 0) + sayIdx
  progressText.value = `${done} / ${total}`
}

watch(open, (v) => {
  if (v) {
    loadEpisode()
    enterLandscape()
  }
  else if (typeof document !== 'undefined') document.body.style.overflow = ''
})

function onKey(e) {
  if (!open.value) return
  if (e.key === 'Escape') close()
  else if (e.key === ' ' || e.key === 'Enter') {
    e.preventDefault()
    if (showChoices.value) return
    if (finished.value) close()
    else next()
  }
}
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<style scoped>
.vn-trigger-wrapper { display: inline-block; vertical-align: middle; }

.vn-play-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: 10px;
  padding: 5px 14px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.02em;
  border-radius: 999px;
  border: 1px solid rgba(99,102,241,0.28);
  background: linear-gradient(135deg, rgba(99,102,241,0.10), rgba(168,85,247,0.10));
  color: #6366f1;
  cursor: pointer;
  vertical-align: middle;
  backdrop-filter: blur(8px);
  transition: all 0.2s cubic-bezier(0.4,0,0.2,1);
}
.vn-play-btn:hover {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  border-color: transparent;
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(99,102,241,0.32);
}
.vn-play-icon { font-size: 10px; }

/* 全屏独占 */
.vn-root {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  background: #02020a;
  outline: none;
}

.vn-stage {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: #060610;
  display: flex;
  flex-direction: column;
  user-select: none;
  -webkit-user-select: none;
}

.vn-bg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: brightness(0.92) saturate(1.05);
}

.vn-bg-fallback {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 30% 18%, rgba(99,102,241,0.22), transparent 58%),
    radial-gradient(ellipse at 78% 82%, rgba(168,85,247,0.16), transparent 60%),
    linear-gradient(180deg, #0f0f1e 0%, #070711 100%);
}

.vn-vignette {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at center, transparent 58%, rgba(0,0,0,0.48) 100%);
  pointer-events: none;
}

/* 角色层 - 透明背景，按插槽定位 */
.vn-characters {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.vn-char {
  position: absolute;
  bottom: 4vh;
  transform: translateX(-50%);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  filter: drop-shadow(0 14px 32px rgba(0,0,0,0.62));
  animation: vn-char-in 0.45s cubic-bezier(0.16,1,0.3,1);
}

@keyframes vn-char-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.vn-char-img {
  height: 100%;
  width: auto;
  max-width: 48vw;
  object-fit: contain;
  object-position: center bottom;
  background: transparent;
}

.vn-char-name-fallback {
  padding: 10px 16px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 12px;
  color: rgba(255,255,255,0.92);
  font-size: 13px;
  backdrop-filter: blur(12px);
}

/* 顶部栏 */
.vn-topbar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: linear-gradient(180deg, rgba(0,0,0,0.58), transparent);
  color: rgba(255,255,255,0.92);
  z-index: 5;
  pointer-events: none;
}
.vn-topbar > * { pointer-events: auto; }
.vn-episode-title {
  font-size: 13px;
  letter-spacing: 0.07em;
  opacity: 0.9;
  font-weight: 600;
}
.vn-top-actions { display: flex; align-items: center; gap: 12px; }
.vn-progress {
  font-size: 12px;
  opacity: 0.65;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.04em;
}
.vn-icon-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.18);
  background: rgba(255,255,255,0.08);
  backdrop-filter: blur(12px);
  color: #fff;
  font-size: 16px;
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: all 0.2s;
}
.vn-icon-btn:hover { background: rgba(255,255,255,0.16); border-color: rgba(255,255,255,0.32); transform: scale(1.05); }

/* 对话 - 不可选中，悬浮毛玻璃卡片 */
.vn-dialog-wrap {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 0 24px 32px;
  display: flex;
  justify-content: center;
  pointer-events: none;
}
.vn-dialog {
  position: relative;
  width: min(820px, 94vw);
  background: rgba(16, 16, 26, 0.84);
  backdrop-filter: blur(20px) saturate(1.25);
  border: 1px solid rgba(255,255,255,0.10);
  border-radius: 18px;
  padding: 20px 24px 18px;
  color: #f0f0f5;
  cursor: pointer;
  pointer-events: auto;
  box-shadow: 0 12px 40px rgba(0,0,0,0.5), 0 1px 0 rgba(255,255,255,0.06) inset;
  transition: transform 0.15s, border-color 0.2s;
  user-select: none;
  -webkit-user-select: none;
}
.vn-dialog:hover { border-color: rgba(255,255,255,0.14); }
.vn-dialog:active { transform: scale(0.995); }
.vn-speaker { display: inline-flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.vn-speaker-name {
  font-weight: 700;
  font-size: 13px;
  letter-spacing: 0.05em;
  color: #fff;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  padding: 4px 11px;
  border-radius: 999px;
  line-height: 1;
  box-shadow: 0 2px 10px rgba(99,102,241,0.35);
}
.vn-text {
  font-size: 15.5px;
  line-height: 1.85;
  font-weight: 400;
  letter-spacing: 0.01em;
  text-shadow: 0 1px 2px rgba(0,0,0,0.35);
  min-height: 1.85em;
  user-select: none;
  -webkit-user-select: none;
}
.vn-next {
  position: absolute;
  right: 16px;
  bottom: 12px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(255,255,255,0.07);
  border: 1px solid rgba(255,255,255,0.10);
  display: grid;
  place-items: center;
}
.vn-next-dot {
  width: 0;
  height: 0;
  border-left: 5px solid rgba(255,255,255,0.92);
  border-top: 4px solid transparent;
  border-bottom: 4px solid transparent;
  margin-left: 1px;
  animation: vn-pulse 1.4s ease-in-out infinite;
}
@keyframes vn-pulse { 0%,100%{opacity:.9;transform:translateX(0)} 50%{opacity:1;transform:translateX(2px)} }
.vn-tap-next { position: absolute; inset: 0; cursor: pointer; z-index: 1; }

/* 选项 - 居中毛玻璃卡片 */
.vn-choices {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(6, 6, 12, 0.62);
  backdrop-filter: blur(14px);
  padding: 24px;
  z-index: 4;
}
.vn-choices-inner { width: min(560px, 92vw); display: flex; flex-direction: column; gap: 11px; }
.vn-choices-hint {
  text-align: center;
  font-size: 11px;
  letter-spacing: 0.22em;
  color: rgba(255,255,255,0.52);
  margin: 0 0 6px;
  text-transform: uppercase;
}
.vn-choice-btn {
  width: 100%;
  text-align: left;
  padding: 14px 18px;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.10);
  background: rgba(255,255,255,0.06);
  backdrop-filter: blur(12px);
  color: rgba(255,255,255,0.94);
  font-size: 14.5px;
  line-height: 1.5;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 14px;
  transition: all 0.22s cubic-bezier(0.16,1,0.3,1);
  box-shadow: 0 2px 12px rgba(0,0,0,0.18);
}
.vn-choice-btn:hover {
  background: rgba(99,102,241,0.20);
  border-color: rgba(99,102,241,0.42);
  transform: translateY(-1px);
  box-shadow: 0 8px 24px rgba(99,102,241,0.28);
}
.vn-choice-btn:active { transform: translateY(0) scale(0.99); }
.vn-choice-index {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: rgba(255,255,255,0.09);
  border: 1px solid rgba(255,255,255,0.12);
  font-size: 12px;
  font-weight: 700;
  color: rgba(255,255,255,0.88);
}
.vn-choice-btn:hover .vn-choice-index { background: #6366f1; border-color: #6366f1; color: #fff; }
.vn-choice-label { flex: 1; }

/* 结束 */
.vn-finished {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(ellipse at center, rgba(18,18,28,0.72), rgba(6,6,12,0.94));
  backdrop-filter: blur(12px);
  z-index: 4;
}
.vn-finished-card {
  text-align: center;
  padding: 36px 32px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.10);
  border-radius: 20px;
  backdrop-filter: blur(16px);
  box-shadow: 0 16px 40px rgba(0,0,0,0.42);
}
.vn-finished-title { font-size: 20px; letter-spacing: 0.14em; color: #fff; margin: 0 0 6px; font-weight: 600; }
.vn-finished-sub { font-size: 13px; color: rgba(255,255,255,0.58); margin: 0 0 22px; letter-spacing: 0.06em; }
.vn-finished-actions { display: flex; gap: 10px; justify-content: center; }
.vn-finished-tip { margin: 18px 0 0; font-size: 12px; color: rgba(255,255,255,0.4); letter-spacing: 0.05em; }
.vn-btn-primary {
  padding: 10px 22px;
  border-radius: 999px;
  border: none;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(99,102,241,0.35);
  transition: all 0.2s;
}
.vn-btn-primary:hover { transform: translateY(-1px); box-shadow: 0 6px 22px rgba(99,102,241,0.45); }
.vn-btn-ghost {
  padding: 10px 22px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.14);
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.88);
  font-size: 14px;
  cursor: pointer;
  backdrop-filter: blur(8px);
  transition: all 0.2s;
}
.vn-btn-ghost:hover { background: rgba(255,255,255,0.10); border-color: rgba(255,255,255,0.22); }

/* 动效 */
.vn-dialog-fade-enter-active, .vn-dialog-fade-leave-active { transition: opacity 0.2s, transform 0.2s; }
.vn-dialog-fade-enter-from { opacity: 0; transform: translateY(8px); }
.vn-dialog-fade-leave-to { opacity: 0; }
.vn-choice-fade-enter-active { transition: opacity 0.25s, transform 0.25s; }
.vn-choice-fade-enter-from { opacity: 0; transform: scale(0.98); }
.vn-fade-enter-active { transition: opacity 0.3s; }
.vn-fade-enter-from { opacity: 0; }
</style>
