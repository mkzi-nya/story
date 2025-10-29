// docs/.vitepress/config.js
import { defineConfig } from 'vitepress'

export default defineConfig({
  base: '/story/',
  title: 'Milthm text',
  description: 'Markdown reader with languages in sidebar',

  themeConfig: {
    nav: [{ text: 'Home', link: '/index' }],
    sidebar: [
      { 
        text: 'Milthm Text', 
        collapsible: true,
        collapsed: false,
        items: [
          {
            text: 'Story',
            collapsible: true,
            collapsed: true,
            items: [
            { text: '简体中文', link: '/story/zh_Hans' },
            { text: '繁體中文', link: '/story/zh_Hant' },
            { text: '粵語', link: '/story/yue_Hant' },
            { text: 'English', link: '/story/en' },
            { text: '日本語', link: '/story/ja' },
            { text: 'Español', link: '/story/es' },
            { text: 'Français', link: '/story/fr' },
            { text: '한국어', link: '/story/ko' },
            { text: 'Русский', link: '/story/ru' },
            { text: 'TiếngViệt', link: '/story/vi' },
            ]
          }
        ]
      },
      {
        text: '二创分区',
        collapsible: true,
        collapsed: false,
        items: [
          {
            text: '创作守则',
            collapsible: true,
            collapsed: true,
            items: [
              { text: 'Milthm 社区衍生内容创作守则', link: 'https://www.milthm.cn/agreement/derivative/' },
              { text: 'Milthm 社区衍生内容创作守则 常见问题解答', link: 'https://milthm.com/wiki/hans/faq/derivative_policy' }
            ]
          },
          { text: '曲绘分析', link: '/fan-made/illustration' },
          {
            text: '长篇文章',
            collapsible: true,
            collapsed: true,
            items: [
              { text: '终焉', link: '/fan-made/articles/demise' },
            ]
          },
          {
            text: '短篇文章',
            collapsible: true,
            collapsed: true,
            items: [
              { text: '樱雨谛', link: '/fan-made/notes/yyd' },
            ]
          },
          {
            text: '整活向',
            collapsible: true,
            collapsed: true,
            items: [
              { text: '舌尖上的卤味鸭', link: '/fan-made/meme/sjsdlwy' },
              { text: 'Milthm野史外传', link: '/fan-made/meme/yeshi' },
              { text: 'Oiiaioooooiai', link: '/fan-made/meme/oiiai' }
            ]
          },
          { text: '按作者索引', link: '/fan-made/author' },
        ]
      }
    ],
    outline: { level: [2, 4] },
    outlineTitle: 'On this page'
  }
})
