# AI广告剪辑项目约定

- 后续项目内容在 `E:/dev/sandbox/AI广告剪辑/` 下构建，按任务建立子目录。
- 项目文档、评估报告、需求、架构、路线图、验收记录和研究结论统一放在 `E:/dev/sandbox/AI广告剪辑/docs/`；根目录仅保留工作区约束、脚本、安装清单和运行配置。
- 严禁调度本地 Docker、WSL、容器或其他虚拟化环境；使用原生 Windows 工具。
- 使用浏览器完成调用后，关闭所有不用的 tab，释放内存。
- 本地只注册一个统一 Skill：`$agent-ffmpeg-local-editor`。17 项能力按需读取其 `references/modules/` 下的内部说明；后续扩展优先增加内部模块，不再注册新的专用 Skill。旧拆分源和既有 `video-cut-` 入口保留用于历史复现。
- 可编辑技能正文、脚本与资源保存在 `skills/`；`C:/Users/carzy/.codex/skills/` 中的对应项是 Windows 目录联接，供 Codex 发现技能。
- 原始仓库快照与 ZIP 保存在 `sources/`，版本、来源与安装映射见 `video-cut-install-manifest.json`。
- 正式本地安装保存在被 Git 忽略的 `local/agent-ffmpeg/`；新命名空间的注册清单为 `agent-ffmpeg-local-install-manifest.json`。安装从已校验发行 ZIP 离线执行，Skill 必须调用该安装版，不能静默回落到源码入口。
- 产品名称统一为 `agent editor kit`。Git 主分支使用 `main`，`origin` 的拉取和推送地址固定为 `git@github.com:copypasteltd/agent-editor-kit.git`；后续代码更新只推送到该仓库。每轮产品更新同时维护三种语言的 README 和相关 `docs/` 文档，通过验证后提交并自动普通推送。
- 每轮功能新增、功能核验和真实样例实测必须同步更新根目录 `README.md` 的编号核验表：记录实际执行内容、结果、日期或证据日期、证据路径及失败/未验收边界。历史测试、当轮实测和研究检查分别标注，不合并计数，不以通过数宣称剪映等价。
- 根目录 `README.md` 为简体中文入口，`README.zh-TW.md` 为繁體中文入口，`README.en.md` 为英文入口；三份 README 须提供相互切换链接，后续产品名、功能、依赖、命令、发布状态和编号核验表须同步维护三种语言。翻译时保留命令、参数、路径、稳定 ID 和链接目标原文。使用手册、Skill 详情、完整案例与发布边界按版本维护在 `docs/releases/`，历史长日志保留归档链接，避免重新堆积到根 README。
- 首个公开预发布为 `v0.1.0-alpha.1`，发布范围是本地 Agent CLI 闭环，完整剪映等价仍是未完成目标。已经公开的标签、附件与对应摘要不得覆盖或强推；新产品更新另建后续版本，并使用普通 `main` 推送。
- 可视功能优先提供原输入和实际输出的短 MP4/GIF；发布到 `docs/assets/` 的演示应具备可公开来源、生成/复现脚本、SHA-256、帧率/时长/帧数和检查记录。模型结果必须来自真实执行；研究动画注明未集成状态，失败样例同样保留。未确认发布权利的素材只链接实测记录。声音、连续播放、抽帧目检和自动检查分别如实说明。
