# 读取订阅与解释结果

## 运行

脚本需要 Python 3.10+。优先复用已有的兼容环境；否则在私有运行目录中建立虚拟环境，再安装本技能的 `scripts/requirements.txt`。无需修改系统 Python 或写入技能目录。一个可选运行位置是 `~/.local/share/deadline-skills/venv`。

从本技能目录运行（将 `python` 换成该环境的解释器）：

```sh
python scripts/read_calendars.py --config ~/.config/deadline-skills/sources.json
```

`--days 14` 可覆盖默认范围；`--start 2026-10-24 --end 2026-11-01` 指定前闭后开的当地日期窗口；带时间的值必须包括 UTC 偏移。`--now` 接受带偏移的当前时间，供固定时间测试或客户端时间覆盖使用。以用户／客户端时间为准，不把示例日期当成今天。运行 `--help` 查看参数。

只查部分来源时，可以在私有临时目录中生成仅含选定来源的配置副本（权限 `600`），保持原配置不变；使用结束后移除该临时副本。不要把私人地址作为命令参数。

## 结果契约

输出 JSON 包含 `checked_at`、`timezone`、`window`、`sources` 和 `candidates`。脚本不保存缓存、不修改配置、不访问网页、不自动判断活动是否为 DDL。

- `sources[].status: ok` 表示该 ICS 本次解析成功。`freshness: fetched_now` 是本次从服务器取得的数据，仍可能存在服务端同步延迟；`snapshot` 是本地导出，`snapshot_at: null` 表示导出时间未知。
- `error`、`pending`、`needs_connector` 和 `needs_agent_read` 都不代表零条截止。`disabled` 不属于本次范围。退出码 `0` 也可能包含单个来源失败，必须检查每项状态。退出码 `2` 表示配置、日期范围或运行环境尚未准备好。
- `candidates` 中的 `due` 已转到显示时区；`due_original` 保留解析值，`precision: date` 必须保持日期精度。`timezone_basis` 为 `source_timezone`／`calendar_timezone`／`display_timezone` 时，原时间未携带明确偏移；向用户说明相关时区依据。
- 用 `uid` 加实例时间识别同一订阅中的重复实例，用任务链接／平台 ID 去除跨源重复。`submission_status: unknown` 是有意保留的未知，不是未提交。
- 脚本处理 `VEVENT` 的重复规则、排除日期、改期与取消。`VTODO` 通过覆盖警告交给另一个支持 `DUE` 的读取工具；不将其静默遗漏。高频重复、无效时区、超大订阅和跨域重定向返回明确缺口，由已知来源工具处理。

脚本依赖成熟的 [icalendar](https://icalendar.readthedocs.io/en/stable/how-to/usage.html) 和 [recurring-ical-events](https://recurring-ical-events.readthedocs.io/en/latest/user-guide/examples.html) 解析器，不用逐行正则假装处理完整 iCalendar 语义。

## 无辅助脚本时

使用已有连接器或已验证的日历解析库，保留时区、仅日期、折行、重复规则及实例例外。无法可靠处理的来源标为未核实。没有依赖或网络不可达时仍可读取独立的连接器／文件来源；不以打开全部网页代替明确报告缺口。
