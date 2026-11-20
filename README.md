# story-video-workflow

把一部虚构小说改编成短视频的工作流：调研 → 写小说 → 分镜表 → 首帧 → 视频 → 帧检 → 旁白 → 字幕 → 拼合 → 校验 → 交付。

> 这是一个**工作流 / 方法仓库**，不是一部影片。本仓库不含任何视频、图片、音频文件，不含小说正文，不含任何密钥。

## 这套流程做过什么

示例影片（完整跑通过一次，2026 年 11 月）：

- 一部根据公开报道改编的虚构小说短片：**63 镜 × 9 秒 = 567 秒（约 9 分半）**
- **9:16 竖屏**，人物二维卡通、环境实景（山、村镇背景用真实地点实拍）
- 旁白 63 句（共 1486 字）+ 全片字幕 + 钢琴弦乐 BGM
- 交付物：一支 540×960 交付版 + 一支 704×1248 高清母版，响度 −14.56 LUFS / 真峰值 −1.24 dBTP
- 生产结果：62/63 镜有视频（1 镜首帧被生成工具安全检查拦下，以黑场配旁白保留镜位）；评级：通过 7 镜、不通过 4 镜、带偏差 51 镜

完整步骤见 [`docs/WORKFLOW.md`](docs/WORKFLOW.md)，模板和脚本见 `templates/`、`scripts/`。

## 适用对象

- 想把一篇小说（或真实事件改编的虚构小说）做成竖屏短视频的个人创作者
- 有一台能跑 ffmpeg、Python 3 的电脑，有图生视频模型和 TTS 工具可用
- 愿意接受“生成模型一定会跑偏，靠帧检和评级管理偏差，而不是追求一次完美”的工作方式

## 流程总览

```
1 调研 ──→ 2 小说 ──→ 3 分镜表 ──→ 4 首帧 ──→ 5 视频 ──→ 6 帧检与评级
                                                              │
7 旁白 TTS ──→ 8 字幕 ──→ 9 拼合与响度 ──→ 10 校验 ──→ 11 交付
```

| 阶段 | 输入 | 输出 |
|---|---|---|
| 1 调研 | 公开报道、来源 | 事件骨架、时间线、纠正清单、绝不能虚构清单 |
| 2 小说 | 调研简报 | 约 8000–10000 字小说（两部分，分两次调用写成）+ 校对记录 |
| 3 分镜表 | 小说 | 63 行分镜表 CSV（9 列），每镜 9 秒 |
| 4 首帧 | 分镜表、实拍参考图 | 每镜一张 1152×2048 首帧 |
| 5 视频 | 首帧 + 动作提示词 | 每镜一支 10.00 秒视频（704×1248，拼合时截前 9 秒） |
| 6 帧检与评级 | 视频 | 逐镜评级（通过 / 带偏差 / 不通过）+ 每批状态文件 |
| 7 旁白 TTS | 分镜表旁白列 | 每句一个 WAV，总时长、各句时长表，超长句重录 |
| 8 字幕 | 分镜表 + 旁白时长 | SRT 字幕 + 镜头映射表 |
| 9 拼合与响度 | 镜头视频 + 旁白 + BGM | 704p 母版 + 540p 交付版，响度达标 |
| 10 校验 | 成片 | 黑帧检测、抽帧、音频淡入淡出、md5、帧数核对 |
| 11 交付 | 成片 | 用户能下载、能播放的交付（原生附件，不走分享链接） |

## 快速开始

1. 读一遍 [`docs/WORKFLOW.md`](docs/WORKFLOW.md)，重点看第 1、3、6、9 阶段和文末的“常见失败模式”与“技术教训”。
2. 按 [`templates/brief-template.md`](templates/brief-template.md) 写你的调研简报（先调研，再写小说）。
3. 用 [`scripts/call-deepseek-novel.py`](scripts/call-deepseek-novel.py) 调小说模型写初稿（密钥只从环境变量读，见脚本说明），再用 [`scripts/proofread-fix.py`](scripts/proofread-fix.py) 做脚本化校对。
4. 按 [`templates/shots-table-template.csv`](templates/shots-table-template.csv) 的 9 列格式做分镜表；旁白格式见 [`templates/narration-list-template.txt`](templates/narration-list-template.txt)。
5. 逐批做首帧 → 视频 → 帧检（每批 4 镜首帧、6 镜视频是实践中验证过的批量上限），评级写入每批状态文件。
6. 旁白、字幕、拼合依次跑 [`scripts/tts-narration.py`](scripts/tts-narration.py)、[`scripts/gen-subs.py`](scripts/gen-subs.py)、[`scripts/build-segments.sh`](scripts/build-segments.sh)、[`scripts/build-final.sh`](scripts/build-final.sh)。

## 仓库结构

```
story-video-workflow/
├── README.md                    # 本文件
├── LICENSE                      # MIT
├── .gitignore                   # 排除视频/图片/音频/密钥/日志
├── docs/
│   └── WORKFLOW.md              # 11 个阶段的完整步骤（核心文档）
├── templates/
│   ├── brief-template.md        # 写小说的简报模板（骨架/纠正/禁写清单/小说要求）
│   ├── shots-table-template.csv # 分镜表模板（9 列 + 3 行示例）
│   └── narration-list-template.txt  # 旁白清单格式示例
└── scripts/
    ├── call-deepseek-novel.py   # 调小说模型，两部分两次调用，密钥只读环境变量
    ├── proofread-fix.py         # 脚本化校对：逐条替换断言 + 禁写/必备检查
    ├── tts-narration.py         # 逐句 TTS，剥离 ID3 标签，报时长，标记超长句
    ├── gen-subs.py              # 由分镜表 + 旁白时长生成 SRT 与镜头映射表
    ├── build-segments.sh        # 每镜 9 秒段落：截取、混音、黑场缺镜、牌面文字（可选）
    └── build-final.sh           # 拼接、烧字幕、混 BGM、淡入淡出、响度、540p + 母版
```

## 三条底线（全流程通用）

1. **事实与虚构分清**：以公开报道为准写情节；内心活动和未证实的生活细节写成明确的虚构演绎，不得写成“据报道”“警方称”。绝不写精确路线、坠落过程、死亡时间、遗体细节。
2. **画面不出现文字**：消息、清单、草稿、寻人启事等内容只用旁白转述，手机屏幕、纸面、牌面在画面里一律无字（牌面文字如必须出现，后期按实测坐标合成，不由生成模型画）。
3. **缺镜不伪造**：生成被拒或被拦的镜头保留镜位（黑场配旁白），等决定重说还是跳过；不拿别的画面顶替，不谎称“全部通过”。

## 许可证

MIT，见 [LICENSE](LICENSE)。

## 联系

仓库维护联系：1718612876@qq.com
