# YOLO Studio - 模型构建平台

类 Roboflow 的 YOLO 目标检测模型构建工具。

## 技术栈

### 后端
- **Python 3.9+** · **FastAPI** · **SQLAlchemy (async)** + **SQLite**
- **Ultralytics** - 真实 YOLO 训练与推理（torch 2.8 + MPS/CPU）
- **Pillow / OpenCV / NumPy** - 图像处理

### 前端
- **Vue 3** (Composition API) · **Element Plus** · **Vue Router 4**
- **Axios** · **Vite**

## 功能模块（全部真实实现，无模拟数据）

| 模块 | 功能 |
|------|------|
| 工程管理 | 创建/删除工程、标注类型（矩形框/多边形）、类别配置、数据集划分比例 |
| 数据集 | 批量上传图片、训练/验证/测试集划分 |
| 图片标注 | 矩形框、**套索（PS 风格自由圈选）**、多边形三种工具；撤销/重做 |
| AI 辅助标注 | 使用 YOLOv8 预训练模型**真实检测**并自动生成标注框（类别自动匹配工程类别） |
| 模型训练 | YOLOv8/YOLO11 多模型选择、**真实 ultralytics 训练**、逐 epoch 进度/指标实时回传 |
| 模型验证 | 真实指标（mAP@50 / mAP@50:95 / Precision / Recall）、训练曲线、混淆矩阵、预测样例等 ultralytics 产物 |
| 测试识别 | 上传图片用**训练好的 best.pt** 真实推理，检测框可视化 |

## 快速启动

### 1. 后端（端口 8000）

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# 或 python main.py
```

API 文档：http://localhost:8000/docs

### 2. 前端（端口 3000）

```bash
cd frontend
npm install
npm run dev
```

前端地址：http://localhost:3000

## 项目结构

```
yolo_builder/
├── backend/
│   ├── api/
│   │   ├── projects.py        # 工程 CRUD
│   │   ├── images.py          # 图片上传/划分
│   │   ├── annotations.py     # 标注 CRUD
│   │   ├── training.py        # 真实 YOLO 训练（线程 + 心跳落库）
│   │   ├── inference.py       # 真实模型推理
│   │   └── ai_annotate.py     # AI 辅助标注（预训练模型检测）
│   ├── core/
│   │   ├── config.py          # 配置
│   │   ├── database.py        # async SQLAlchemy
│   │   └── dataset.py         # YOLO 数据集导出（数据库 → data.yaml + labels）
│   ├── models/                # Project / Image / Annotation / TrainRun
│   ├── data/                  # 运行时数据（uploads / models / outputs）
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/index.js       # API 封装
│   │   ├── views/             # 7 个页面
│   │   ├── components/        # TrainingChart / ConfusionMatrix
│   │   └── assets/styles/     # 全局样式（工业风）
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## 真实训练说明

- 训练前自动把数据库标注导出为 YOLO 格式（`outputs/{project}/dataset/`）
- 标注类别索引与 `project.classes` 顺序一致
- 多边形标注自动取外接矩形参与检测训练
- 验证集为空时自动从训练集借一张（ultralytics 要求 val 非空）
- 训练进度通过回调实时写入数据库，前端每 2 秒轮询
- 权重保存于 `outputs/{project}/run_{id}/weights/best.pt`，推理自动优先加载

## 标注快捷键

| 操作 | 说明 |
|------|------|
| 矩形框 | 按住左键拖拽 |
| 套索 | 按住左键自由圈选，松开闭合（矩形工程转外接矩形，多边形工程存自由形状） |
| 多边形 | 逐点点击，双击闭合 |
| `Ctrl+Z` / `Ctrl+Shift+Z` | 撤销 / 重做 |
