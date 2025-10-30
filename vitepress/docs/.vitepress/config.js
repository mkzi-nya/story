// docs/.vitepress/config.js
import { defineConfig } from 'vitepress'

export default defineConfig({
  base: '/story/',
  title: 'Home',
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
            { text: '简体中文', link: '/milthm/story/zh_Hans' },
            { text: '繁體中文', link: '/milthm/story/zh_Hant' },
            { text: '粵語', link: '/milthm/story/yue_Hant' },
            { text: 'English', link: '/milthm/story/en' },
            { text: '日本語', link: '/milthm/story/ja' },
            { text: 'Español', link: '/milthm/story/es' },
            { text: 'Français', link: '/milthm/story/fr' },
            { text: '한국어', link: '/milthm/story/ko' },
            { text: 'Русский', link: '/milthm/story/ru' },
            { text: 'TiếngViệt', link: '/milthm/story/vi' },
            ]
          },
          {
            text: 'Raingpt',
            collapsible: true,
            collapsed: true,
            items: [
            { text: '欢迎', link: '/milthm/raingpt/welcome' },
            { text: '又又又又断触了<span class="fav">❤</span>', link: '/milthm/raingpt/judgement' },
            { text: '雨丝的机制<span class="fav">❤</span>', link: '/milthm/raingpt/hold-tricks' },
            { text: '游戏机制细节<span class="fav">❤</span>', link: '/milthm/raingpt/level-rule' },
            { text: 'Reality<span class="fav">❤</span>', link: '/milthm/raingpt/reality' },
            { text: '星星<span class="fav">❤</span>', link: '/milthm/raingpt/star' },
            { text: '蓝牙耳机<span class="fav">❤</span>', link: '/milthm/raingpt/bluetooth' },
            { text: '“绮梦”玩法<span class="fav">❤</span>', link: '/milthm/raingpt/character-guidence' },
            { text: '你是谁?', link: '/milthm/raingpt/who-are-you' },
            { text: '倾盆大雨是什么', link: '/milthm/raingpt/what-is-downpour' },
            { text: '那个“❤”是什么', link: '/milthm/raingpt/what-is-heart' },
            { text: '下午茶', link: '/milthm/raingpt/coffee' },
            { text: '被砍了怎么办?', link: '/milthm/raingpt/susan' },
            { text: '哄我睡觉', link: '/milthm/raingpt/sleep' },
            { text: '你知道吗?', link: '/milthm/raingpt/do-you-know' },
            { text: '还是场景原画师', link: '/milthm/raingpt/or-scene-illustration' },
            { text: '奖励', link: '/milthm/raingpt/rain' },
            { text: '/查询 精神状态', link: '/milthm/raingpt/checkstate' },
            { text: '关于制作团队', link: '/milthm/raingpt/about-us' },
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
              { text: 'Oiiaioooooiai', link: '/fan-made/meme/oiiai' },
              { text: '神秘小习俗', link: '/fan-made/meme/custom' }
            ]
          },
          { text: '按作者索引', link: '/fan-made/author' },
        ]
      }
    ],
    outline: { level: [2, 4] },
    outlineTitle: '导览'
  }
})
