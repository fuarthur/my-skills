# Deadline Skills

两个配套技能：一次接入来源，之后直接查询近期 DDL。可独立于课程工作区使用，也适用于项目、报名和其他个人截止事项。

| 技能 | 用途 |
| --- | --- |
| [setup-deadline-sources](setup-deadline-sources/SKILL.md) | 询问来源入口、范围及时区，接入 Canvas、已连接日历、iCal／ICS 订阅或文件，保存私人配置。 |
| [check-deadlines](check-deadlines/SKILL.md) | 刷新已保存来源，筛选截止事项，按时间输出简洁清单。 |

## 安装

从仓库根目录复制两个完整目录：

```sh
mkdir -p ~/.codex/skills
cp -R deadlines/setup-deadline-sources ~/.codex/skills/
cp -R deadlines/check-deadlines ~/.codex/skills/
```

ICS 辅助工具需要 Python 3.10+ 和 `check-deadlines/scripts/requirements.txt` 中的依赖，首次使用时可在私有虚拟环境中安装；仅使用日历连接器时不依赖此脚本。运行说明见 [reading.md](check-deadlines/references/reading.md)。

## 使用

- `用 $setup-deadline-sources 初始化我的 DDL 来源，我使用 Canvas 和 Google Calendar。`
- `用 $setup-deadline-sources 添加这个日历订阅链接。`
- `用 $check-deadlines 看看最近的 DDL。`
- `用 $check-deadlines 列出未来两周 CS101 的截止事项。`

初始化时可以直接提供订阅链接，也可以授权 agent 从已登录的指定页面代找现有链接。已连接日历可直接复用。私人配置默认保存在 `~/.config/deadline-skills/sources.json`，与技能源码分开；不要将完整私有订阅地址提交到仓库。

“最近”默认是含今天的 7 个当地日期，也可以更改。查询只输出截止清单；本地 ICS 保持快照标记，来源失败或日期不明保持可见，提交状态不会从本地成稿或日历中推断。需要一周学习安排时使用 `plan-coursework-week`。

## 验证

使用已装日历依赖的 Python，在仓库根目录运行：

```sh
python -m unittest discover -s deadlines/tests -p 'test_*.py' -v
```

测试使用虚构日历，不访问私人账号。覆盖时间窗口、仅日期、时区换算、夏令时、重复规则、改期／取消、部分失败与私人订阅地址保护。
