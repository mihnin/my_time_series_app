<template>
  <div class="sidebar">
    <Navigation @page-change="handlePageChange" />
    <TrainingSettings v-if="currentPage === 'Главная'" />
    <SaveResults :isVisible="store.predictionRows.length > 0" />
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue'
import Navigation from './Navigation.vue'
import TrainingSettings from './TrainingSettings.vue'
import SaveResults from './SaveResults.vue'
import { useMainStore } from '../stores/mainStore'

export default defineComponent({
  name: 'Sidebar',
  components: {
    Navigation,
    TrainingSettings,
    SaveResults
  },
  props: {
    currentPage: {
      type: String,
      required: true
    },
    handlePageChange: {
      type: Function,
      required: true
    }
  },
  setup() {
    const store = useMainStore()
    return { store }
  }
})
</script>

<style scoped>
.sidebar {
  width: 400px;
  min-width: 400px;
  background-color: #f5f5f5;
  padding: 1rem;
  border-right: 1px solid #ddd;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  overflow-y: auto;
  z-index: 10;
  box-sizing: border-box;
}
</style>
