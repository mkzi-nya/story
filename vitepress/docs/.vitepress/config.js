// docs/.vitepress/config.js
import { defineConfig } from 'vitepress'

export default defineConfig({
  base: '/story/',
  title: 'Milthm story text',
  description: 'Markdown reader with languages in sidebar',

  themeConfig: {
    nav: [{ text: 'Home', link: '/index' }],
    sidebar: [
      { 
        text: 'Milthm Story', 
        collapsible: true,
        collapsed: true,
        items: [
        { text: '简体中文', link: '/zh_Hans' },
        { text: '繁體中文', link: '/zh_Hant' },
        { text: '粵語', link: '/yue_Hant' },
        { text: 'English', link: '/en' },
        { text: '日本語', link: '/ja' },
        { text: 'Español', link: '/es' },
        { text: 'Français', link: '/fr' },
        { text: '한국어', link: '/ko' },
        { text: 'Русский', link: '/ru' },
        { text: 'TiếngViệt', link: '/vi' },
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
          { text: '曲绘分析', link: '/illustration' },
          {
            text: '长篇文章',
            collapsible: true,
            collapsed: true,
            items: [
              { text: '终焉', link: '/demise' },
            ]
          },
          {
            text: '短篇文章',
            collapsible: true,
            collapsed: true,
            items: [
              { text: '樱雨谛', link: '/yyd' },
            ]
          },
          {
            text: '整活向',
            collapsible: true,
            collapsed: true,
            items: [
              { text: '舌尖上的卤味鸭', link: '/sjsdlwy' },
              { text: 'Milthm野史外传', link: '/yeshi' },
              { text: 'Oiiaioooooiai', link: '/oiiai' }
            ]
          }
        ]
      }
    ],
    outline: { level: [2, 4] },
    outlineTitle: 'On this page'
  }
})
