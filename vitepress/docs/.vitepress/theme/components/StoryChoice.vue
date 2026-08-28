<template>
  <div class="story-choice">
    <div class="story-choice-options">
      <button
        v-for="(opt, i) in options"
        :key="i"
        :class="['story-choice-btn', { active: i === selected }]"
        @click="selected = i"
      >{{ opt }}</button>
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
  margin: 18px 0;
  padding: 14px 16px;
  border-left: 3px solid var(--vp-c-brand);
  border-radius: 8px;
  background: var(--vp-c-bg-alt);
}
.story-choice-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.story-choice-btn {
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid var(--vp-c-divider);
  background: var(--vp-c-bg);
  color: var(--vp-c-text-1);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.story-choice-btn:hover {
  border-color: var(--vp-c-brand);
}
.story-choice-btn.active {
  background: var(--vp-c-brand);
  border-color: var(--vp-c-brand);
  color: #fff;
}
.story-choice-content {
  margin-left: 12px;
  padding-left: 12px;
  border-left: 1px dashed var(--vp-c-divider);
}
</style>
