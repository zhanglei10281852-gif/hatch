# 离线复现与证据来源

项目：pypa/hatch；题目：pypa-hatch-4d2944d3-33d3-4f4b-be6c-536ed3afd32a。

核心验证在 Windows / Python 3.11.7 下执行，使用全新工具 venv、每场景全新 Hatch data/cache、uv no-cache，以及独立 Git fixture。没有复用作者的 research-venv 或构建缓存。offline/ 的六个固定 wheel 是构建环境唯一依赖来源；其中 Hatchling 从登记基线的 backend 源码实际构建，其他为预下载的固定 wheel。offline-tools/ 提供本次 Windows 工具 venv 的完整 wheel 材料，包括 uv、pytest 和安装依赖。版本、文件大小和 SHA256 见 offline-manifest.json。

创建一个空 Python 3.11 venv，然后运行（PowerShell，当前位置项目根部）：

```powershell
Copy-Item evidence/bootstrap/_version.py src/hatch/_version.py
python -m venv F:\hatch-review-tools
F:\hatch-review-tools\Scripts\python.exe -m pip install --no-index --find-links evidence/offline-tools -r evidence/tooling-requirements.txt
F:\hatch-review-tools\Scripts\python.exe -m pip install --no-index --find-links evidence/offline --force-reinstall hatchling==1.33.0
F:\hatch-review-tools\Scripts\python.exe evidence/verify.py
F:\hatch-review-tools\Scripts\python.exe evidence/verify-extra.py
```

脚本各自创建全新临时 scratch，或使用 HATCH_REVIEW_WORK 指定一个新建空目录；不在生产代码中注入逻辑。主脚本预期 21 场景 67 断言、4 个 Rubric 6 失败断言；extra 脚本预期 4 场景 15 断言全部通过。原始执行路径、输出、事件、产物前后 SHA256 和创建环境路径在 verification.json / verification-extra.json。脚本携带真实 backend hook：只记录事件和按 fail-metadata 输入抛异常，不替换生产 selector、Git、metadata、subprocess 或后端构建。

脚本启动只拒绝不转发的本地代理；Python 子进程 socket.connect 禁止非 loopback，uv 同时 offline/no-index/no-cache，pip no-index/local links。所有环境继承限制。network-proof.json 保存两个真实拒绝探针：Python 到 1.1.1.1 的 socket 被拒绝；原生 uv 请求 example.com wheel 的 CONNECT 被代理拒绝。探针不安装分发；随后核心运行只使用本地 wheel。network-denied.jsonl 是实际 Python 拒绝日志。工具 wheel 的预下载不属于核心验收执行阶段。

补充单测命令：

```powershell
$env:PYTHONPATH=(Join-Path $PWD src)
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
F:\hatch-review-tools\Scripts\python.exe -m pytest tests/cli/build -m 'not requires_internet' -p pytest_mock -p no:cacheprovider -q
```

结果为 30 passed / 31 deselected。未选取的网络标记单测不用于支持通过；相应构建入口、默认 all/单项目、双 target 和显式输出在真实离线 CLI 中验证。早期验证器的夹具配置、顺序断言和旧 sentinel 文件名错误在 work/hatch-delivery-review 留档；不计入模型失败，交付 JSON 无 driverError。

frozen-input.json 固定原 Prompt、7 条 Rubric、基线、Session 和扫描轮数证据。原始 session Markdown 与 metadata 为同一次模型运行的导出桥材料；未重跑模型。scan-evidence-check.json 只核对扫描保存的 65 轮，未调用计数脚本。session-duration.json 和 session-renderer-evidence.txt 记录当前完整 Session 实际开始/完成日志，2024 秒，不超过两小时。production-integrity.json 记录 547 文件未被复盘改写。fork-api.json 验证登记个人 Fork 的 parent 与 ADMIN 权限。

verify-rubric.yaml 使用工作台 delivery-package.mjs 的 buildVerifyRubricYaml 生成，并由同文件的 validateVerifyRubricYaml 及 yaml.parseDocument 实际解析；verify-rubric-validation.json 保存 ID/type/text/顺序一致性。页面/服务端 payload 同样调用此 builder。未改冻结标准。

rubric-comparison.txt 是实际结论报告。01-rubric-comparison.png 是 Agent 从承载同一报告及原始证据摘要的专用终端客户区使用 CopyFromScreen 捕获，非文字绘图；保存后视觉复核。当前 Codex 面板混有工具调用与其他消息，使用仅本题的终端备用区域。

model.patch 从唯一登记基线生成，包含新增文件和二进制证据；仅排除补丁本身，避免递归。项目根部 .git 保留。个人 Fork commit 用于保存代码和证据，不表示远程题目交付；本轮只复盘，后续 delivery_qc 独立执行。
