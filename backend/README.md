# AI4Math-Evolving Bridge (Stdlib 后端，无 FastAPI 依赖)

这个后端负责把前端的 upload/start/stop/event 事件对接到 OpenEvolve 的项目目录演化流程。

## 端口与目录

- 默认监听：`127.0.0.1:8001`
- 数据根目录：`AI4Math-Evolving/server_data/`

## 启动

```bash
export LLM_API_KEY=
export LLM_BASE_URL=https://chat.ecnu.edu.cn/open/api/v1
export LLM_MODEL_ID=ecnu-plus

export DEEPSEEK_API_KEY=
python3 backend/server.py
```

如果你只想做上传/列出项目（不点 START），provider key 可以不设置。结果分析会优先读取 `LLM_*`，再回退到 `DEEPSEEK_*`；现有 OpenEvolve 示例仍可能校验 `DEEPSEEK_API_KEY`。

## API（供前端使用）

- `GET /api/projects`
  - 列出 `server_data/` 下可用的 evolve object 项目（需要根目录存在 `initial_program.py` / `evaluator.py` / `config.yaml` 或 `config_default.yaml`）。

- `POST /api/projects/upload`（multipart/form-data）
  - 表单字段：
    - `zip`：上传的 zip 文件
    - `projectName`：落盘目录名（如果你前端不传，后端会从 zip 文件名推断）

- `POST /api/runs/start`（application/json）
  - 请求体：
    - `projectName`: evolve 对象项目名（目录名）
    - `iterations`: 演化迭代次数（UI 的 generations 映射）
    - `checkpointInterval`: checkpoint 落盘间隔（每 N 轮保存一次）

- `POST /api/runs/{runId}/stop`
  - 停止当前 run（SIGTERM -> 必要时 SIGKILL）

- `GET /api/runs/{runId}/events`
  - SSE 事件流
  - 事件类型目前以：
    - `log`（最佳适应度等）
    - `done`（任务结束）
  为主

## zip 结构约定

上传 zip 后端会“归一化”到项目根目录，因此你可以：
- 让 zip 根目录直接包含 `initial_program.py` / `evaluator.py` / `config.yaml`
或
- zip 内可以多一层目录/嵌套，后端会递归找所需文件并移动到项目根。
