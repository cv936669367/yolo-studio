# 界面截图占位目录

README.md 引用了以下 6 张截图，**将你的截图按此命名放入本目录即可显示**：

| 文件 | 内容建议 |
|------|---------|
| `01-projects.png` | 工程列表（卡片网格） |
| `02-dataset.png` | 数据集管理（图片网格 + 筛选 + 上传面板） |
| `03-annotate.png` | 图片标注（画布 + AI 辅助 + 智能分割 + 垂直工具条） |
| `04-train.png` | 模型训练（模型选择 + 参数 + 实时日志） |
| `05-evaluate.png` | 模型验证（指标 + 曲线 + 多模型切换 + 导出） |
| `06-test.png` | 测试识别（上传图片 + 检测框） |

生成截图小技巧（Chrome 无头）：

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --screenshot=docs/screenshots/01-projects.png \
  --window-size=1600,950 --virtual-time-budget=6000 "http://localhost:3000/projects"
```
