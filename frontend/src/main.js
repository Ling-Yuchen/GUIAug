import { createApp } from 'vue'
import { createDiscreteApi } from 'naive-ui'
import App from './App.vue'

// createApp(App).mount('#app')

const app = createApp(App)

// 创建 message API
const { message } = createDiscreteApi(['message'])
app.config.globalProperties.$message = message

app.mount('#app')
