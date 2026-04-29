import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './design/fonts.css'
import './design/tokens.css'
import './design/globals.css'
import './design/motion.js'

const app = createApp(App)

app.use(router)

app.mount('#app')
