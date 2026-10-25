# 私人来源配置（version 1）

默认文件为 `~/.config/deadline-skills/sources.json`。先读再合并，保留未知字段。此文档是配置契约；技能仓库中不放使用者的实际配置。

最小配置：

```json
{
  "version": 1,
  "timezone": "America/Chicago",
  "default_days": 7,
  "sources": []
}
```

示例时区仅用于说明格式，实际值取自用户上下文。`default_days` 是含今天的当地日期数量；检查从当前时刻开始，直到第 N 个日期结束。来源允许部分可用，`sources` 为空表示尚未接入。

每项来源使用以下字段：

| 字段 | 含义 |
| --- | --- |
| `id`, `label` | 稳定的本地标识、用户可读名称；ID 唯一 |
| `kind` | `ics`、`ics_file`、`calendar`、`web` 或 `file` |
| `status` | `ready`、`pending` 或 `disabled` |
| `scope` | 用户选定的课程／项目／日历及排除范围 |
| `deadline_rule` | 混合日历如何识别截止；专门的 DDL 日历可写“全部事件为截止事项” |
| `timezone` | 可选，来源的 IANA 时区；没有时区的时间使用它，否则使用顶层时区并注明推定 |
| `last_verified_at` | 上次实际成功验证的带时区 ISO 时间，失败不更新 |
| `coverage_notes` | 未覆盖任务类型、同步延迟、访问缺口等已知限制 |
| `browser_access` | `not_authorized` 或 `read_only`；只在确有相关授权时记录后者 |
| `authorization_note` | 可选，用户允许代找／读取的范围及日期；不替代平台权限 |

按 `kind` 增加对应定位字段：

- `ics`：`feed_url`（HTTPS 或 `webcal://` 订阅地址）。辅助脚本把 webcal 转成 HTTPS。完整地址按凭据保护。
- `ics_file`：`path`（本地 ICS 绝对路径），已知时填写 `snapshot_at`（导出时间）。这是快照，不是实时订阅。
- `calendar`：`provider`、`calendar_id`，必要时保存账号选择提示，不保存登录令牌。
- `web`：`page_url`、简短 `read_method`。记录授权范围内需要访问的入口，不保存 cookies。
- `file`：`path`、`read_method`；说明表格、Markdown 或其他本地资料中的截止字段。文件更新时间不能证明平台仍未改期。

`provider: "canvas"` 可以用于标识 Canvas 来源。`scope` 和 `deadline_rule` 由读取技能判断，ICS 脚本只负责提取时间候选，不自动把活动分类为 DDL。日历连接器及网页由 agent 按配置另行读取。

例：一项已验证的订阅应保存 `id`、`label`、`kind: "ics"`、`status: "ready"`、私有 `feed_url`、范围、筛选规则及验证时间。没有取得地址或权限时保存 `pending` 和缺口，不能填入猜测的地址。

初始化完成的判断是：至少一个来源已成功试读，其他来源的缺口明确。配置文件存在但所有来源均 `pending` 时，只能说“配置已保存，接入未完成”。
