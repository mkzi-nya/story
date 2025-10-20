// docs/.vitepress/config.js
import { defineConfig } from 'vitepress'

export default defineConfig({
  base: '/story/',
  title: 'Milthm story text',
  description: 'Markdown reader with languages in sidebar',

  themeConfig: {
    nav: [{ text: 'Home', link: '/index' }],
    sidebar: [
      { text: 'Milthm Story', items: [{ text: 'Languages', link: '/index' }] },
      {
        text: '二创分区',
        items: [{ text: '曲绘分析', link: '/illustration' }]
      },
      {
        text: '其他文章',
        items: [{ text: 'Milthm 社区衍生内容创作守则', link: 'https://www.milthm.cn/agreement/derivative/' },{ text: 'Milthm 社区衍生内容创作守则 常见问题解答', link: 'https://milthm.com/wiki/hans/faq/derivative_policy' }]
      }    ],
    outline: { level: [2, 4] },
    outlineTitle: 'On this page'
  }
})
