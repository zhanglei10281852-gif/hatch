# Hatch 交付质检记录

题目 pypa-hatch-4d2944d3-33d3-4f4b-be6c-536ed3afd32a。读取开始修订号6；本次主动刷新远端预检后为7。原 Prompt、冻结7条标准、Session、轮数及模型生产文件均保持不变。质检修复仅限复现脚本跨平台路径、Linux 离线材料与质检证据。

## 场景与环境适配

核心入口是实际 `python -m hatch build --all --changed-since REF`，涉及本地 Git 差异、工作区成员、静态/动态元数据与 Python wheel/sdist 构建。每个 fixture 创建普通目录中的 Git 仓库和 pyproject，后端为真实 Hatchling，custom hook 只记录清理/构建/metadata 事件及按文件输入抛出真实异常。候选和动态元数据逻辑未被 mock。

核心子进程仅执行 Git、Python 和 uv；构建类型是 virtual 环境，不涉及 Docker 环境。tests/conftest.py:240 的 devpi fixture 含 Docker Compose 启动逻辑，但它不是 autouse，本题核心驱动不调用 pytest fixture，补充选取的构建单测不请求 devpi。没有 testcontainers、数据库容器、挂载、FUSE、云账号或外部业务服务依赖。唯一测试接收端是脚本内只拒绝连接且不转发的 loopback HTTP 代理。共享参考允许的纯本地文件、普通用户权限与预置离线分发覆盖了题目全部核心生产契约。WSL 分发名称含 docker 字样不作为容器服务使用；本次执行入口是该 Linux 用户空间的 Python/Git，没有调用 Docker CLI 或 socket。

## 离线补齐与实际运行

发现 reviewer 工具材料仅覆盖 Windows，且驱动写死 uv.exe。已在原项目的 evidence/verify.py 和 verify-extra.py 按 os.name 选择可执行名，并追加 distro 的 Linux 条件依赖。预下载并登记 musl/Python3.12 和 glibc/Python3.11 的固定 wheel；全部 SHA256 见 offline-manifest.json。没有修改 src、backend、模型测试、Prompt 或 Rubric。

实际平台 Alpine 3.22.1，Python 3.12.15，uv 0.13.7，Linux x86_64。准备期系统 uv 创建全新工具 venv；此后安装只使用交付目录内 wheel，工具与每场景 data/cache 隔离，uv no-cache。

```sh
uv venv --python /usr/bin/python3 /tmp/hatch-qc-4d2944d3-tools
uv pip install --python /tmp/hatch-qc-4d2944d3-tools/bin/python --offline --no-index --no-cache --find-links evidence/offline-tools -r evidence/tooling-requirements.txt distro==1.9.0
uv pip install --python /tmp/hatch-qc-4d2944d3-tools/bin/python --offline --no-index --no-cache --find-links evidence/offline --force-reinstall hatchling==1.33.0
HATCH_REVIEW_WORK=/tmp/hatch-qc-4d2944d3-primary /tmp/hatch-qc-4d2944d3-tools/bin/python evidence/verify.py
HATCH_REVIEW_WORK=/tmp/hatch-qc-4d2944d3-extra /tmp/hatch-qc-4d2944d3-tools/bin/python evidence/verify-extra.py
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/hatch-qc-4d2944d3-tools/bin/python -m pytest tests/cli/build -m 'not requires_internet' -p pytest_mock -p no:cacheprovider -q
```

主驱动退出0，21场景67断言，63通过，4项失败是 duplicate-orphan-1/2 与 metadata-orphan-1/2，无驱动错误。额外驱动退出0，4场景15断言全部通过。补充单测退出0，30 passed、31 deselected。全部核心入口真实执行，没有以未选取测试支持通过。安装材料预下载不属于核心验证阶段；原阿里镜像下载停滞后改为官方索引，所用平台材料准备完成后才执行离线安装和核心验证，未把下载问题判为模型缺陷。

每个核心命令继承 Python socket.connect 公网拒绝、只拒绝不转发的代理与 uv offline/no-index/no-cache。linux-network-proof.json 记录真实 Python 子进程到1.1.1.1被拒绝，原生uv下载的CONNECT被本地代理拒绝；不是只声明环境变量。

## 双向复核和静态门禁

重新读取真实构建入口、Workspace.members、Project.get_dependencies、prepare_build_environment、BuildFrontend 与实际运行轨迹，核对登记基线和作者变更。状态/调用顺序仍与 code-audit.md 一致。模型主路径可用；共享文件全选提前返回位于名称歧义及元数据检查之前。Linux 重验再次观察到同名包清理/构建返回0，以及 a 清理并重建后 z-dynamic 元数据失败返回1。该失败属于原题明确的“任何项目制品构建或清理之前”的预检要求；不增加构建后回滚或选择性 clean 契约。保留部分完成，标准1-5、7通过，6未通过。

扫描证据仍为 Trae/count-trae-cn-steps.py/latest_turn/当前完整Session，65轮，主步骤65、子代理0、工具批次65、回复0、压缩0；未运行计数脚本。时长脚本按完整Session重新执行，起止时间、2024秒、否、Realtime来源及renderer两处行号与记录一致，见本目录 session-duration.json。时长不影响完成度或收录。

静态检查实际解析严格YAML并比对全部7项id/type/text和顺序，逐条核对三处结果与详细报告，全部一致。页面/服务端发送字段使用同一 buildVerifyRubricYaml。真实性说明为用户场景、仓库适配及工程难点，没有基线能力盘点。主要语言Python、任务类型功能新增、question_type为有效轮数小于100且效果差，seed_model来自工作台固定配置。

远端预检刷新返回 matched=true、PRECHECK_PASSED，批次 e1f51f763d2d49a0a6b265324a930e2a、条目9986；原始检测输入的Repo和完整Prompt与本题逐字一致，见 precheck-proof.json。个人Fork通过GitHub API复核 isFork=true、parent为pypa/hatch且当前身份ADMIN；最终修复证据提交推送后再次核验完整Commit地址。

唯一真实报告图已打开视觉复核：全部7条、期望、观察、直接证据、失败原因/影响/位置及原始摘要完整；只有本题专用终端客户区，无其他应用或取景UI，无大面积空白。图与原reviewer记录SHA256一致，不重用其他题/Session。未改变结论，因此保留这张最终图。

基线补丁随新增离线材料和质检证据重新生成，包含二进制及新增文件，仅排除model.patch自身防递归，并执行反向应用检查。原547个非evidence文件SHA256仍一致；根部.git保留。个人Fork提交只保存产物，未冒充远程提交。通过后进入delivery_production，真实远程交付另行执行。
