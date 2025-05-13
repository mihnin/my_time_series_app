<template>
  <nav class="navigation">
    <div class="nav-buttons">
      <button 
        v-for="page in pages" 
        :key="page"
        @click="$emit('page-change', page)"
        :class="{ active: currentPage === page }"
      >
        {{ page }}
      </button>
    </div>
  </nav>
</template>

<script lang="ts">
import { defineComponent, ref } from 'vue'

export default defineComponent({
  name: 'Navigation',
  emits: ['page-change'],
  setup() {
    const currentPage = ref('Главная')
    const pages = ['Главная', 'Анализ данных', 'Help']

    return {
      currentPage,
      pages
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
  background-color: #4CAF50;
  color: white;
}
</style>