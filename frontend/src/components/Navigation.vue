<template>
  <nav class="navigation">
    <div class="nav-buttons">
      <button 
        v-for="page in pages" 
        :key="page"
        @click="$emit('page-change', page)"
        :class="{ active: page === currentPage }"
      >
        {{ page }}
      </button>
    </div>
  </nav>
</template>

<script lang="ts">
import { defineComponent, toRefs } from 'vue'
export default defineComponent({
  name: 'Navigation',
  props: {
    currentPage: {
      type: String,
      required: true
    }
  },
  emits: ['page-change'],
  setup(props) {
    const pages = ['Обучение', 'Инструкция']
    const { currentPage } = toRefs(props)
    return {
      pages,
      currentPage
    }
  }
})
</script>

<style scoped>
.navigation {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.nav-buttons {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

button {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 4px;
  background-color: #f0f0f0;
  cursor: pointer;
  transition: background-color 0.2s;
}

button:hover {
  background-color: #e0e0e0;
}

button.active {
  background-color: #4CAF50 !important;
  color: white !important;
}
</style>