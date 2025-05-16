<template>
  <div class="training-settings">
    <FileUploader @file-loaded="handleFileLoaded" />
    <ColumnSelector :is-visible="hasLoadedFile" />
    <MissingValueHandler 
      :is-visible="hasLoadedFile" 
      :available-static-features="staticFeatures"
    />
    <FrequencySettings :is-visible="hasLoadedFile" />
    <MetricsAndModels :is-visible="hasLoadedFile" />
    <Training :is-visible="hasLoadedFile" />
    <Prediction :is-visible="hasLoadedFile" />
    <SaveResults :is-visible="hasLoadedFile" />
    <AppLogs :is-visible="hasLoadedFile" />
    <ModelExport :is-visible="hasLoadedFile" />
  </div>
</template>

<script lang="ts">
import { defineComponent, computed } from 'vue'
import { useMainStore } from '../stores/mainStore'
import FileUploader from './FileUploader.vue'
import ColumnSelector from './ColumnSelector.vue'
import MissingValueHandler from './MissingValueHandler.vue'
import FrequencySettings from './FrequencySettings.vue'
import MetricsAndModels from './MetricsAndModels.vue'
import Training from './Training.vue'
import Prediction from './Prediction.vue'
import SaveResults from './SaveResults.vue'
import AppLogs from './AppLogs.vue'
import ModelExport from './ModelExport.vue'

export default defineComponent({
  name: 'TrainingSettings',
  
  components: {
    FileUploader,
    ColumnSelector,
    MissingValueHandler,
    FrequencySettings,
    MetricsAndModels,
    Training,
    Prediction,
    SaveResults,
    AppLogs,
    ModelExport
  },

  setup() {
    const store = useMainStore()

    const hasLoadedFile = computed(() => 
      store.tableData.length > 0 && 
      store.selectedFile !== null)
    const staticFeatures = computed(() => store.staticFeatures)

    const handleFileLoaded = () => {
      // Reset any previous selections
      store.setDateColumn('<нет>')
      store.setTargetColumn('<нет>')
      store.setIdColumn('<нет>')
      store.setStaticFeatures([])
      store.setFillMethod('None (оставить как есть)')
      store.setGroupingColumns([])
      store.setHorizonUnit('D (день)') // сбрасываем единицу измерения по умолчанию
      store.setSelectedMetric('SQL (Scaled quantile loss)')
      store.setSelectedModels(['*'])
      store.setSelectedPreset('high_quality')
      store.setPredictionHorizon(3)
      store.setTimeLimit(null)
      store.setMeanOnly(false)
      store.setTrainPredictSave(false)
    }

    return {
      hasLoadedFile,
      staticFeatures,
      handleFileLoaded
    }
  }
})
</script>

<style scoped>
.training-settings {
  width: 100%;
}
</style>