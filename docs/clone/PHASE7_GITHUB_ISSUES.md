# 第七期 GitHub 任务索引

Epic：[[Epic] ATBOffice 第七期：工具栏细节、Ledger 交互、稳定性与文档兼容完善](https://github.com/aitobox/ATBOffice/issues/234)。

核验日期：2026-11-04。已创建 1 个 Epic 和 13 个子任务，逐项回读确认标题、正文、标签一致，全部为 open。

依据 [第七期计划](../tasks/07_phase7_fidelity_stability_compatibility_plan.md) 与 [详细任务卡](CLONE_DIFF.md)。GitHub Epic 内嵌计划快照，各子任务含文件范围、验收清单、测试命令及全局约束，远端阅读不依赖尚未推送的本地文档。

| 任务 | GitHub Issue | 类型 | 优先级 | 依赖 |
|---|---|---|---|---|
| TASK-701 | [#235 test(evidence): 重建可信截图与功能验收基线](https://github.com/aitobox/ATBOffice/issues/235) | `enhancement` | `priority:high` | 无 |
| TASK-702 | [#236 fix(files): 修复假成功并事务化文件打开](https://github.com/aitobox/ATBOffice/issues/236) | `bug` | `priority:high` | [#235](https://github.com/aitobox/ATBOffice/issues/235) |
| TASK-703 | [#237 fix(stability): 基于操作序列治理崩溃与对象生命周期](https://github.com/aitobox/ATBOffice/issues/237) | `bug` | `priority:high` | [#235](https://github.com/aitobox/ATBOffice/issues/235) |
| TASK-704 | [#238 test(corpus): 建立逐文件内容与显示合同](https://github.com/aitobox/ATBOffice/issues/238) | `enhancement` | `priority:high` | [#235](https://github.com/aitobox/ATBOffice/issues/235) |
| TASK-705 | [#239 fix(quire): 修复 Strict DOCX 空白及真实排版差异](https://github.com/aitobox/ATBOffice/issues/239) | `bug` | `priority:high` | [#236](https://github.com/aitobox/ATBOffice/issues/236), [#238](https://github.com/aitobox/ATBOffice/issues/238) |
| TASK-706 | [#240 fix(ledger-io): 修复 XLSX/XLSM 默认保存丢失](https://github.com/aitobox/ATBOffice/issues/240) | `bug` | `priority:high` | [#236](https://github.com/aitobox/ATBOffice/issues/236), [#238](https://github.com/aitobox/ATBOffice/issues/238) |
| TASK-707 | [#241 fix(ledger-render): 修复真实工作簿载入后的显示与同步](https://github.com/aitobox/ATBOffice/issues/241) | `bug` | `priority:high` | [#238](https://github.com/aitobox/ATBOffice/issues/238), [#240](https://github.com/aitobox/ATBOffice/issues/240) |
| TASK-708 | [#242 fix(lectern): 按真实样本修复幻灯片显示及往返](https://github.com/aitobox/ATBOffice/issues/242) | `bug` | `priority:high` | [#236](https://github.com/aitobox/ATBOffice/issues/236), [#238](https://github.com/aitobox/ATBOffice/issues/238) |
| TASK-709 | [#243 fix(ledger-menu): 补齐右键菜单的真实业务行为](https://github.com/aitobox/ATBOffice/issues/243) | `bug` | `priority:high` | [#235](https://github.com/aitobox/ATBOffice/issues/235) |
| TASK-710 | [#244 fix(ledger-fill): 恢复填充柄完整事件链与保护事务](https://github.com/aitobox/ATBOffice/issues/244) | `bug` | `priority:high` | [#243](https://github.com/aitobox/ATBOffice/issues/243) |
| TASK-711 | [#245 fix(toolbar): 逐控件校准图标箭头状态与命中区域](https://github.com/aitobox/ATBOffice/issues/245) | `bug` | `priority:high` | [#235](https://github.com/aitobox/ATBOffice/issues/235) |
| TASK-712 | [#246 fix(commands): 清理可见空行为并完善动态本地化](https://github.com/aitobox/ATBOffice/issues/246) | `bug` | `priority:high` | [#245](https://github.com/aitobox/ATBOffice/issues/245) |
| TASK-713 | [#247 test(acceptance): 以真实用户路径完成第七期验收](https://github.com/aitobox/ATBOffice/issues/247) | `enhancement` | `priority:high` | [#237](https://github.com/aitobox/ATBOffice/issues/237), [#239](https://github.com/aitobox/ATBOffice/issues/239), [#241](https://github.com/aitobox/ATBOffice/issues/241), [#242](https://github.com/aitobox/ATBOffice/issues/242), [#244](https://github.com/aitobox/ATBOffice/issues/244), [#246](https://github.com/aitobox/ATBOffice/issues/246) |

依赖与 Blocks 已双向回填到 issue 正文；Epic 使用交互任务清单跟踪全部子任务。机器可读映射见 [PHASE7_GITHUB_ISSUES.json](PHASE7_GITHUB_ISSUES.json)。

状态机中已有 `active_epic: 212`（第六期），依 skill 非破坏规则保留；未自动切换、关闭旧 Epic 或启动实现。第七期可从 TASK-701 / #235 开始。

此次只创建 issues 并回填本地文档，没有提交或推送代码。
