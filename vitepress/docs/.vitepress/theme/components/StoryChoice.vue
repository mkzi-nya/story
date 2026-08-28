<template>
  <div class="story-choice">
    <div class="story-choice-options">
      <button
        v-for="(opt, i) in options"
        :key="i"
        :class="['story-choice-btn', { active: i === selected }]"
        @click="selected = i"
      >
        <span class="sc-idx">{{ String.fromCharCode(65 + i) }}</span>
        <span class="sc-label">{{ opt }}</span>
      </button>
    </div>
    <div class="story-choice-content">
      <slot v-if="selected === 0" name="branch-0" />
      <slot v-else-if="selected === 1" name="branch-1" />
      <slot v-else-if="selected === 2" name="branch-2" />
      <slot v-else-if="selected === 3" name="branch-3" />
      <slot v-else-if="selected === 4" name="branch-4" />
      <slot v-else-if="selected === 5" name="branch-5" />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  options: { type: Array, required: true },
  default: { type: Number, default: 0 }
})

const selected = ref(props.default || 0)
</script>

<style scoped>
.story-choice {
  margin: 20px 0;
  padding: 16px 16px 14px;
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(99,102,241,0.06), rgba(168,85,247,0.04));
  border: 1px solid rgba(99,102,241,0.12);
  backdrop-filter: blur(6px);
}

.story-choice-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.story-choice-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 14px 7px 8px;
  border-radius: 999px;
  border: 1px solid var(--vp-c-divider);
  background: var(--vp-c-bg);
  color: var(--vp-c-text-1);
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.16,1,0.3,1);
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}

.story-choice-btn:hover {
  border-color: rgba(99,102,241,0.35);
  background: rgba(99,102,241,0.06);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99,102,241,0.12);
}

.story-choice-btn.active {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border-color: transparent;
  color: #fff;
  box-shadow: 0 4px 14px rgba(99,102,241,0.35);
}

.sc-idx {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: rgba(0,0,0,0.06);
  border: 1px solid rgba(0,0,0,0.06);
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

html.dark .sc-idx {
  background: rgba(255,255,255,0.08);
  border-color: rgba(255,255,255,0.08);
}

.story-choice-btn.active .sc-idx {
  background: rgba(255,255,255,0.22);
  border-color: rgba(255,255,255,0.22);
  color: #fff;
}

.sc-label {
  line-height: 1.3;
}

.story-choice-content {
  margin-left: 6px;
  padding: 12px 14px 4px 16px;
  border-left: 2px solid rgba(99,102,241,0.18);
  background: rgba(255,255,255,0.42);
  border-radius: 0 10px 10px 0;
}

html.dark .story-choice-content {
  background: rgba(255,255,255,0.04);
  border-left-color: rgba(99,102,241,0.28);
}

.story-choice-content :deep(ul) {
  margin: 0;
  padding-left: 1.2em;
}

.story-choice-content :deep(li) {
  margin: 6px 0;
  line-height: 1.7;
}
</style>
