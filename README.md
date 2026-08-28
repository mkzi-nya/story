# [https://mkzi-nya.github.io/story/](https://mkzi-nya.github.io/story/)
该网页展现了 Milthm 游戏剧情内容及一些二创文章，欢迎投稿

该网页完全为玩家制作，与官方并无关联

## 投稿途径：
- QQ: 510334363
- QQ: [2450382239](https://qm.qq.com/q/UfEfmy7MEE)
- 或直接向此仓库提交 PR（`vitepress/docs/fan-made`）

---

This webpage presents the storyline content of the Milthm game and some fan-created articles. Submissions are welcome.

## Submission methods:
- Discord: [mkzi_nya](https://discordapp.com/users/1135097559891853435)
- Or directly submit a pull request to this repository

---

## 项目结构

```
story/
├── vitepress/                 # vitepress 站点源码
│   ├── docs/
│   │   ├── .vitepress/
│   │   │   ├── config.js      # 站点/路由/目录配置
│   │   │   ├── theme/         # 主题与自定义组件（VnPlayer 等）
│   │   │   └── dist/          # vitepress 构建产物（部署时生成）
│   │   ├── milthm/story/      # 剧情页（markdown + VnPlayer 入口）
│   │   ├── milthm/raingpt/    # RainGPT 相关页面
│   │   ├── fan-made/          # 玩家二创文章页
│   │   └── public/            # 站点静态资源
│   └── node_modules/          # 本地构建依赖（不入库）
├── vn-assets/                 # VN 运行时资源，播放器直接引用 /story/vn-assets/...
│   ├── character/             # 立绘（透明烘焙 .webp，按角色分目录）
│   ├── background/            # 背景（.avif）
│   ├── audio/                 # 音频（bgm/ bgs/ snd/，.ogg）
│   └── scripts/               # 剧本 JSON（每集一个）
├── files/                     # raingpt 相关静态文件
├── update.py                  # 更新脚本：解析 milthm_unpack 源数据，
│   │                           #   生成剧本 JSON/页面、烘焙立绘、转换音频、
│   │                           #   编译 vitepress 到仓库根目录
├── 1.sh                       # 旧版构建/发布辅助脚本
└── README.md
```

构建/更新流程：`update.py` 从仓库外的
`milthm_unpack/`（源数据，不参与构建、不入库）读取 AVG 剧本与素材，
生成 `vitepress/docs/milthm/story/*`、`vn-assets/scripts/*.json`，烘焙/转换
资源（`vn-assets/`）并清理更新后不再引用的文件，最后编译 vitepress 把产物
拷贝到 `story/` 根目录直接发布。依赖只在 `update.py` 里使用 VN 插件时生成；
`vitepress/node_modules` 为本地构建依赖，不入库。