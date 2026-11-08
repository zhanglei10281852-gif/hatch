# 按 Git 变更闭包筛选 workspace 构建

> **Workspace:** F:\swe\099928\project-02

---

**User**

修改 monorepo 中的共享库后，维护者希望构建该库及受它影响的本地包，并跳过没有关联的包。请给 hatch build --all 增加 --changed-since REF，以 REF 指向的 Git 提交与当前工作树中已跟踪文件的差异选择构建项目，包含提交后的变更、暂存及未暂存修改，不把未跟踪文件当作变化，也不自动改用合并基点。候选范围沿用所选环境的 workspace.members 和 exclude，有 project 表的根项目也作为候选且最多出现一次，只有 workspace 配置的根目录不生成自身制品；该模式仅适用于所有成员都位于同一个 Git 工作树的情况，并要求与 --all 一起使用。变化文件归属于包含它的最深层成员目录，目录名相似或路径含空格不能造成误判；删除文件仍影响原所属成员，跨成员重命名要考虑旧、新两条路径。若有已跟踪文件变化不属于任何成员目录，则保守选择全部候选项目。对成员内的变化，还须加入直接或间接依赖受影响项目的其他候选项目：依据各项目当前解析出的运行时依赖和全部可选依赖，按 PEP 503 规范化后的包名建立关系，版本约束、环境标记及可选组是否启用均不缩减这个保守影响范围，不查询包索引求解依赖，动态依赖通过现有元数据解析流程取得；依赖环应结束计算，每个入选项目只构建一次。成员和依赖关系必须足以确定完整集合后才能开始生成制品；REF 无效、成员不在同一工作树、规范化包名有歧义或依赖元数据解析失败时，给出可定位的错误并且不开始任何项目的制品构建或清理，修复输入后再次执行应按新输入重新计算。没有已跟踪文件变化时成功退出，说明无需构建，不准备构建环境，也不改动已有制品。入选项目沿用 --all 的构建顺序、目标选择和统一输出位置，未传 --changed-since 时，单项目 build 与全量 build --all 的既有行为保持不变。

**Assistant**

我先回顾相关经验，然后探索仓库结构。

toolName: view_folder

status: success

f:\swe\099928\project-02

这是 Hatch 仓库。我先建立任务清单，然后阅读核心实现文件。

toolName: todo_write

status: success

Todos updated: 5 items

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\src\hatch\cli\build\__init__.py

现在阅读项目核心与 workspace 相关实现。

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\src\hatch\project\core.py

继续查看 workspace 配置、环境接口以及现有测试。

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\tests\workspaces\test_config.py

toolName: search_by_regex

status: success

Workspace 配置不在 project/config.py，搜索其定义位置。

toolName: search_by_regex

status: success

toolName: search_by_regex

status: success

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\src\hatch\env\plugin\interface.py

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\tests\cli\build\test_build.py

继续阅读 TestBuildAll 部分。

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\tests\cli\build\test_build.py

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\src\hatch\utils\metadata.py

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\src\hatch\dep\core.py

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\tests\conftest.py

查看 Platform.run_command 与 Application 的实现。

toolName: search_by_regex

status: success

toolName: search_by_regex

status: success

toolName: search_by_regex

status: success

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\src\hatch\cli\application.py

查看现有 git 调用模式与 Path 工具类。

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\src\hatch\config\model.py

toolName: search_by_regex

status: success

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\src\hatch\utils\fs.py

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\src\hatch\utils\dep.py

toolName: search_by_regex

status: success

查看 pyproject 配置、文档以及现有使用 git 的测试模式。

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\pyproject.toml

toolName: search_by_regex

status: success

toolName: search_by_regex

status: success

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\ruff.toml

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\backend\src\hatchling\metadata\core.py

toolName: search_by_regex

status: success

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\docs\build.md

查看 CLI 参考文档中的 build 部分与 EnvironmentInterface.root 定义。

toolName: search_by_regex

status: success

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\src\hatch\env\plugin\interface.py

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\docs\cli\reference.md

toolName: search_by_regex

status: success

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\docs\history\hatch.md

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\docs\how-to\environment\workspace.md

查看 Terminal 的显示方法与 platform 的其余辅助方法。

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\src\hatch\cli\terminal.py

查看 platform.py 的进程调用细节，确认编码与捕获方式。

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\src\hatch\utils\platform.py

信息已足够。更新任务清单并开始设计实现，先看一下现有“无操作”提示的措辞习惯。

toolName: todo_write

status: success

Todos updated: 5 items

toolName: search_by_regex

status: success

toolName: search_by_regex

status: success

toolName: search_by_regex

status: success

设计已清晰。先确认 ruff 默认规则（行长、测试中的魔法数等），然后动手实现。

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\ruff_defaults.toml

规则明确了。开始实现前最后确认 `ensure_environment_plugin_dependencies` 的行为，保证离线测试安全。

toolName: search_by_regex

status: success

现在开始实现。更新任务状态并重写 build 命令模块。

toolName: todo_write

status: success

Todos updated: 6 items

toolName: Write

status: success

filePath: f:\swe\099928\project-02\src\hatch\cli\build\__init__.py

changes: undefined

去掉多余的包装函数，直接在选择器内惰性导入规范化函数。

toolName: edit_file_search_replace

status: success

filePath: f:\swe\099928\project-02\src\hatch\cli\build\__init__.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: f:\swe\099928\project-02\src\hatch\cli\build\__init__.py

changes: undefined

核心实现完成。现在检查测试环境，然后编写测试。

toolName: Shell

status: success

toolName: Shell

status: success

toolName: Shell

status: success

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\hatch.toml

toolName: Shell

status: success

导入的不是工作区版本，检查实际加载路径。

toolName: Shell

status: success

toolName: search_by_regex

status: success

`hatch.cli.build` 名字被 click 命令对象遮蔽，改用 `from ... import` 验证。

toolName: Shell

status: success

现在确认 `hatch new` 默认模板的目录布局，以便编写端到端测试。

toolName: search_by_regex

status: success

toolName: search_by_regex

status: success

默认是 src 布局。现在编写完整的测试文件。

toolName: Write

status: success

filePath: f:\swe\099928\project-02\tests\cli\build\test_changed_since.py

changes: undefined

现在运行新增的测试（通过 PYTHONPATH 指向工作区源码）。

toolName: Shell

status: success

全局 pytest 插件冲突，禁用外来插件后重试。

toolName: Shell

status: success

toolName: Shell

status: success

toolName: Shell

status: success

全局插件污染严重，改用禁用自动加载并显式启用所需插件。

toolName: search_by_regex

status: success

toolName: Shell

status: success

27 个通过，2 个联网 e2e 失败。查看完整失败原因确认是否为环境问题。

toolName: Shell

status: success

失败是环境缺少 `trove_classifiers` 依赖，与本次逻辑无关。尝试补齐依赖以运行完整 e2e。

toolName: Shell

status: success

网络可用。重新运行 e2e 测试看下一个缺口。

toolName: Shell

status: success

toolName: Shell

status: success

toolName: Shell

status: success

全部 29 个测试通过。现在回归现有 build 测试。

toolName: todo_write

status: success

Todos updated: 6 items

toolName: Shell

status: success

59 通过，唯一错误是环境缺 `uv`（既有测试，与改动无关）。安装后重跑确认。

toolName: Shell

status: success

全部 60 个 build 测试通过。现在运行 ruff 检查代码风格。

toolName: Shell

status: success

toolName: Shell

status: success

toolName: view_files

status: success

filePath: C:\Users\czxy4\AppData\Local\Temp\trae-agent-toolhost\jobs\job-f3749b0359104d4baf68f19459a1b2e4\output.log

toolName: search_by_regex

status: success

toolName: Shell

status: success

查看 CI 固定的 ruff 版本，决定 noqa 取舍。

toolName: search_by_regex

status: success

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\scripts\update_ruff.py

按本地 ruff（CI 跟踪最新版）修正所有问题。

toolName: edit_file_search_replace

status: success

filePath: f:\swe\099928\project-02\src\hatch\cli\build\__init__.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: f:\swe\099928\project-02\src\hatch\cli\build\__init__.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: f:\swe\099928\project-02\tests\cli\build\test_changed_since.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: f:\swe\099928\project-02\tests\cli\build\test_changed_since.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: f:\swe\099928\project-02\tests\cli\build\test_changed_since.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: f:\swe\099928\project-02\tests\cli\build\test_changed_since.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: f:\swe\099928\project-02\tests\cli\build\test_changed_since.py

changes: undefined

toolName: Shell

status: success

静态检查通过。复跑测试确认改动无回归，并检查 CLI 帮助输出。

toolName: Shell

status: success

补一个通过 click 全链路验证错误提示（invalid REF → abort）的离线 CLI 测试。

toolName: edit_file_search_replace

status: success

filePath: f:\swe\099928\project-02\tests\cli\build\test_changed_since.py

changes: undefined

toolName: Shell

status: success

测试全部通过。现在更新文档：变更历史与 workspace 使用指南。

toolName: edit_file_search_replace

status: success

filePath: f:\swe\099928\project-02\docs\history\hatch.md

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: f:\swe\099928\project-02\docs\how-to\environment\workspace.md

changes: undefined

文档完成。通读最终实现文件做一次完整自查。

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\src\hatch\cli\build\__init__.py

toolName: view_files

status: success

filePath: f:\swe\099928\project-02\src\hatch\cli\build\__init__.py

实现自查通过。最后完整复跑整个 build 测试目录确认全绿。

toolName: Shell

status: success

全部 61 个测试通过。做最后的诊断检查并收尾任务清单。

toolName: todo_write

status: success

Todos updated: 6 items

toolName: GetDiagnostics

status: success

已完成 `hatch build --all --changed-since REF` 功能的实现，全部测试与静态检查通过。

## 改动概览

**核心实现**：[build/__init__.py](file:///f:/swe/099928/project-02/src/hatch/cli/build/__init__.py)

- 新增 `--changed-since REF` 选项（[L40-L49](file:///f:/swe/099928/project-02/src/hatch/cli/build/__init__.py#L40-L49)），未配合 `--all` 使用时在准备构建环境前直接报错退出（[L112-L114](file:///f:/swe/099928/project-02/src/hatch/cli/build/__init__.py#L112-L114)）。
- 选择逻辑集中在 [select_changed_projects](file:///f:/swe/099928/project-02/src/hatch/cli/build/__init__.py#L179-L244)，在任何制品生成或清理之前完成完整集合计算。

**需求对照**：

- **变化集合**：`git diff --name-only --no-renames -z REF`（[L282-L296](file:///f:/swe/099928/project-02/src/hatch/cli/build/__init__.py#L282-L296)）直接比较 REF 与工作树（不用合并基点），自然涵盖提交后变更、暂存与未暂存修改，不含未跟踪文件；`-z` 保证含空格路径不被转义；`--no-renames` 让跨成员重命名产生旧路径删除+新路径新增两条记录。
- **候选范围**：沿用所选环境的 `workspace.members`/`exclude`，有 `project` 表的根项目作为候选且只出现一次（复用现有候选构造，[L138-L141](file:///f:/swe/099928/project-02/src/hatch/cli/build/__init__.py#L138-L141)）。
- **同一工作树校验**：对每个候选执行 `git rev-parse --show-toplevel` 并比较，含非 Git 目录或多工作树均给出定位错误（[L247-L270](file:///f:/swe/099928/project-02/src/hatch/cli/build/__init__.py#L247-L270)）。
- **归属判定**：按 `normcase+abspath` 后的目录边界匹配最深层成员目录（[L299-L325](file:///f:/swe/099928/project-02/src/hatch/cli/build/__init__.py#L299-L325)），相似目录名（`foo`/`foobar`）、空格、删除文件、跨成员重命名均有测试覆盖；任何变化文件无法归属时保守构建全部候选。
- **反向依赖传播**：通过现有 `Project.get_dependencies()`（动态依赖走既有元数据解析流程，不查包索引）取运行时依赖加**全部** optional-dependencies，按 PEP 503 规范化包名建边，版本约束/环境标记/可选组是否启用均不缩减范围；BFS + visited 集合保证环终止、每项目只构建一次，并保持 `--all` 原顺序（[L220-L244](file:///f:/swe/099928/project-02/src/hatch/cli/build/__init__.py#L220-L244)）。
- **错误处理**：REF 无效（`rev-parse --verify REF^{commit}`）、跨工作树、规范化包名歧义、依赖元数据解析/解析失败均抛出可定位错误，不开始任何构建或清理；无 Git 可执行文件也有明确提示。
- **无变化**：成功退出并提示 `No tracked file changes detected since ..., nothing to build`，不准备构建环境、不触碰已有制品（[L151-L153](file:///f:/swe/099928/project-02/src/hatch/cli/build/__init__.py#L151-L153)）。
- 未传该选项时，单项目与全量 `--all` 路径完全不变；入选项目沿用原构建顺序、目标选择与统一输出目录。

**测试**：新增 [test_changed_since.py](file:///f:/swe/099928/project-02/tests/cli/build/test_changed_since.py)，共 30 个用例：脚本化 Git 的纯单元测试（归属、依赖传播、环、歧义、各类错误）、真实 Git 仓库的语义测试（暂存/未暂存/未跟踪/删除/跨成员重命名/孤立文件）、以及 CLI 端到端测试（选项互斥、无效 REF、无变化零副作用、变更子集与反向依赖实际产物校验）。`tests/cli/build/` 全部 61 个测试通过，ruff 检查无告警。

**文档**：[history/hatch.md](file:///f:/swe/099928/project-02/docs/history/hatch.md#L9-L13) Unreleased 增加条目，[workspace.md](file:///f:/swe/099928/project-02/docs/how-to/environment/workspace.md#L88-L100) 新增“Building only what changed”小节；CLI 参考文档由 click help 自动生成。
