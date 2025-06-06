<template>
  <div class="sidebar">
    <Navigation :current-page="currentPage" @page-change="$emit('page-change', $event)" />
    <div class="sidebar-separator"></div>
    <TrainingSettings v-if="currentPage === 'Обучение'" />
    <DbSettingsButton />
  </div>
</template>

<script lang="ts">
import { defineComponent, toRefs } from 'vue'
import Navigation from './Navigation.vue'
import TrainingSettings from './TrainingSettings.vue'
import DbSettingsButton from './DbSettingsButton.vue'
import { useMainStore } from '../stores/mainStore'

export default defineComponent({
  name: 'Sidebar',
  components: {
    Navigation,
    TrainingSettings,
    DbSettingsButton
  },
  props: {
    currentPage: {
      type: String,
      required: true
    }
  },
  emits: ['page-change'],
  setup(props) {
    const store = useMainStore()
    const { currentPage } = toRefs(props)
    return { 
      store,
      currentPage
    }
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
  z-index: 5;
  box-sizing: border-box;
}
.sidebar-separator {
  height: 1px;
  background: #ddd;
  margin: 1rem 0;
}
</style>
