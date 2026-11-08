# Hatch changed-since 交付代码审计

题目 pypa-hatch-4d2944d3-33d3-4f4b-be6c-536ed3afd32a。唯一模型运行是 frozen-input.json 记录的 Trae Session；未重新运行模型。基线 740565ac2929597cb9def8d46338cbef6493fc8d。代码审计和 CLI 验证均使用该次运行后的项目文件；547 个非 evidence 文件与复盘前 SHA256 一致。

## 入口、所有者与边界

- 外部入口 `src/hatch/cli/build/__init__.py:18-176` 是 Click build 命令。默认单项目分支保持 `_build_project`；all 分支从当前环境的 Workspace 获取成员，真实根项目先放入候选，按 location 排除成员中的根项目重复项。容器根没有 project 表，候选不含根。
- Workspace 是当前环境候选配置的所有者。`src/hatch/env/plugin/interface.py:1249-1410` 展开 members、exclude 和 glob，检查成员项目文件并保留原有顺序。glob 同一条目按目录 basename 排序，所以 closure 的候选顺序是 client、core、final；它不是拓扑顺序。选中环境的成员使用合法 builder 环境配置，实际只构建 b。
- `select_changed_projects:179-251` 先检查所有候选 Git 根、REF 对象，再获取直接差异。`_verify_git_reference:274` 使用 REF^{commit}；`_get_changed_paths:283` 使用 `git diff --name-only --no-renames -z REF`，不使用 merge-base。Git 的树到工作树差异包含已提交、暂存、未暂存变化，不读取未跟踪文件。direct-diverged-ref 实际把只存在于 REF 分支的 a 与当前分支的 b 都选中。
- `_attribute_changed_paths:299-325` 规范化绝对路径，以目录分隔符判断包含关系并取最长成员路径。删除旧路径仍归属，禁用 rename 合并后，跨成员 rename 的旧、新路径各自进入归属。deep-paths 与 rename-delete 验证了真实 Git 差异和最终 wheel。
- 依赖图由本次命令局部字典、队列、visited 集合持有。`_get_project_dependency_names:328-357` 合并运行时与全部可选依赖，仅读取规范化 requirement.name，不裁剪版本、marker 或 optional 组。反向边与 visited 闭包返回原候选顺序，每个项目至多一次。
- `src/hatch/project/core.py:301-321` 是依赖元数据的生产边界：静态依赖读取 core_raw_metadata；dynamic 则准备构建环境并调用现有 build_frontend。`src/hatch/project/frontend/core.py`、`frontend/scripts/core_metadata.py` 经实际后端进程取得 metadata；fixture 的真实 MetadataHook 记录事件并抛出 CONTROLLED_METADATA_FAILURE。没有替换此生产函数或进程。
- 制品与清理由 `_build_project:378-460` 所有。它先 `prepare_build_environment`，然后在项目工作目录与构建环境中执行实际 hatchling build 子进程，传递 target、统一绝对 output、clean 等开关。`Project.prepare_build_environment:258-299` 与 virtual env 的依赖同步使用预置 wheel；真实构建 hook 记录 initialize/clean 事件，真实 wheel 的 METADATA 被打开检查。

## 失败时序与重试

成员内变化分支：候选检查 -> REF/diff -> 路径归属 -> 全候选名称映射 -> 全候选依赖元数据 -> 闭包 -> 制品构建。invalid-ref、cross-tree、duplicate-member-change 与 metadata-member-change 均返回 1，零制品构建；旧制品保留。删除 fail-metadata 后，同一 fixture/state 再调用命令返回 0，仅构建 a，证明重新读取当前输入。无变化在动态解析之前返回 0，未创建构建环境、没有后端事件、旧制品哈希不变。

共享文件分支的确定缺口：`src/hatch/cli/build/__init__.py:200-201` 的 `if affected_projects is None: return list(projects)` 位于名称映射及依赖元数据预检之前。调用者把这个列表当作完整计划，直接进入 `_build_project`。

1. duplicate-orphan-1/2：容器根共享文件已跟踪变化，包名 dupe.name 与 dupe-name 同时存在。两个名字按 PEP503 同为 dupe-name。实际事件为 a clean-wheel -> a build-wheel -> b clean-wheel -> b build-wheel，退出 0，没有名称歧义错误。旧同名 wheel SHA256 从 6a021447... 变为 4f8b11b8...。
2. metadata-orphan-1/2：共享变化后，a 在前，z-dynamic 后端 hook 读取 fail-metadata 并抛错。事件为 a clean-wheel -> a build-wheel -> z-dynamic metadata，退出 1，stderr 包含 RuntimeError: CONTROLLED_METADATA_FAILURE。旧 a wheel SHA256 从 6a021447... 变为 153f4b14...。完整元数据解析之前，a 制品已清理和重建。

这两条触发条件属于 Prompt 明文要求：共享文件全候选选择与无效输入前不得开始任何制品构建/清理同时成立。未引入构建开始后的全局回滚、选择性 clean、拓扑排序、网络依赖求解或历史成员恢复义务。不是以基线已有的默认 clean 行为独立判失败；失败是新选择器绕过了题面要求的构建前检查。

本任务是一次同步 CLI 计划与构建；没有持久化 API 提交、并发请求、后台 worker、取消 deadline 或网络会话生命周期要求。生产子进程经平台执行/等待返回后才继续下个项目，未新增异步线程。这里适用的资源顺序是元数据预检与制品清理/构建的边界，上述真实可控 hook 故障覆盖它；不增加无来源的并发契约。

## 证据与结论

verification.json 的 21 场景 67 断言中 63 通过、4 失败；失败是上述两种场景各两次。verification-extra.json 的 4 场景 15 断言全部通过。pytest-build.log 为补充单测 30 通过、31 个网络标记测试未选取；这 30 项不是核心验收的替代。核心由不 mock 的实际 CLI、Git、动态元数据、离线安装和 Hatchling 制品构建验证。

Rubric 1、2、3、4、5、7 通过；6 未通过。可用选择/构建主路径存在，完成度部分完成；扫描保存的 65 轮不变，收录为难题。完整三处规范结果见 rubric-results.json、artifact-result.txt、run-result.txt；逐条详细证据见 rubric-comparison.txt。
