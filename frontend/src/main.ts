import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

import './styles/fonts.css'
import './styles/tokens.css'
import './styles/base.css'

const app = createApp(App)
app.use(createPinia()) // before the router, so navigation guards can use stores
app.use(router)
app.mount('#app')
