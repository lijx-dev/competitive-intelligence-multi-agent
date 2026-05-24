# 代码修改提交说明

> 提交人：Silen  
> 日期：2026-05-23  
> 关联任务：队长分配 — 修 bug / 补测试 / 换模型 / 03 方案接入

---

## 一、修改总览

本次提交完成 **4 大任务**，共修改/新建 **10 个文件**，全部通过测试验证。

| 任务 | 文件数 | 测试 |
|---|---|---|
| 模型配置统一 | 5 | 通过 |
| 反馈闭环修复 | 4 | 通过 |
| 核心路径测试 | 1（新建） | 6 个 case 全部通过 |
| 03 方案接入主系统 | 4 | 2 个 case 全部通过 |

---

## 二、详细修改清单

### 任务 1：模型配置统一（换官方模型）

**背景**：原代码混用 `doubao-seed-1-8-251228`，统一为官方提供的 `doubao-seed-2.0-lite`。

| 文件 | 修改内容 |
|---|---|
| **`.env`**（根目录新建） | `LLM_MODEL=doubao-seed-2.0-lite`、`DOUBAO_MODEL_ID=doubao-seed-2.0-lite`、`DOUBAO_MAX_CONTEXT_TOKENS=256000`（从 32000 上调匹配官方规格），填入实际 API Key 和飞书 Webhook |
| **`python/src/config.py`** | `LLMConfig.model` 默认值改为 `"doubao-seed-2.0-lite"`；`LLMConfig.doubao_model_id` 默认值改为 `"doubao-seed-2.0-lite"` |
| **`python/src/services/llm/doubao_client.py`** | `DoubaoLLM.__init__` 的 `model_id` 默认参数改为 `"doubao-seed-2.0-lite"` |
| **`python/src/services/llm/llm_factory.py`** | `_get_doubao_llm` 的 fallback model_id 改为 `"doubao-seed-2.0-lite"` |
| **`python/.env.example`** | 保留原样（作为模板参考），实际运行以根目录 `.env` 为准 |

**验证**：`grep -r "doubao-seed-1-8-251228" python/src/` 无残留。

---

### 任务 2：反馈闭环修复（防"伪闭环"）

**背景**：原反馈循环 `Reviewer → TargetedFix → Reviewer` 存在"伪闭环"风险——修复后评分未真正提升，循环却结束。

| 文件 | 修改内容 |
|---|---|
| **`python/src/graph/workflow.py`** | `_after_review` 增加 `partial completion` 分支：3 次修复后仍 `<7` 分，设置 `state["battlecard_partial_completion"]=True` 并继续流程（不阻塞） |
| **`python/src/agents/targeted_fix_agent.py`** | `__call__` 增加 `fix_history` 累积，记录每轮修复前的 `score_before` 和 `issues_count_before` |
| **`python/src/agents/reviewer_agent.py`** | `__call__` 增加逻辑：若 `fix_history` 存在且最后一轮 `score_after` 为 0，则填入当前 `feedback.overall_score` 并计算 `improvement` |
| **`python/src/models/schemas.py`** | 新增 `FixEffectiveness` 数据类，字段：`round`/`score_before`/`score_after`/`issues_count_before`/`issues_count_after`/`improvement`/`fixed_fields` |

---

### 任务 3：核心路径测试（新建）

**文件**：`python/tests/test_core_paths.py`（新建）

| 测试类 | 验证内容 |
|---|---|
| `TestFeedbackLoop` | fix_effectiveness 记录、reviewer 更新 score_after/improvement、partial completion 标记 |
| `TestFeishuSignature` | HMAC-SHA256 签名算法正确性、推送失败不阻塞主流程 |
| `TestRAGRecall` | 文档入库 + 查询召回验证 |
| `TestModelConfigUnified` | 配置默认模型验证、源码中无硬编码旧模型 ID |
| `TestDAGRouting` | Reviewer 后条件边路由（score<7→TargetedFix、score≥7→Citation、3 次后→partial completion） |
| `Test03FrameworkIntegration` | 03 模块可导入、增强方法返回非空（见任务 4） |

**运行方式**：
```bash
cd python
PYTHONPATH=$(pwd) python3 -m pytest tests/test_core_paths.py -v
```

---

### 任务 4：03 方案接入主系统

**背景**：03 方案的 `weight_fusion_engine.py` 和 `competitive_intelligence_framework.py` 已复制到 `python/src/services/`，但未被主系统调用。本次将其接入 CompareAgent。

| 文件 | 修改内容 |
|---|---|
| **`python/src/agents/compare_agent.py`** | **核心改动**：<br>1. 新增导入两个 03 模块（try-except 保护，缺失时自动跳过）<br>2. 新增 `_enrich_research_data()` 方法，三步增强：<br>　　① **口碑情感分析**：提取 research_results 中 sentiment/review/口碑 topic，用 `ReputationAssessmentFramework`（规则版，不依赖 transformers）做批量情感分析<br>　　② **数据可达性评估**：调用 `DataAccessibilityMatrix` 输出 A/B/C/D 类数据覆盖度<br>　　③ **多源冲突检测**：按 topic 分组检查同一维度下不同来源的置信度差异，差异 >0.3 标记冲突<br>3. `compare()` 方法在调用 LLM 前注入增强文本区块，LLM 收到冲突/低置信度提示后会自动降低对应维度评分 |
| **`python/src/services/competitive_intelligence_framework.py`** | 将 sklearn、statsmodels 的导入改为 try-except 模式，缺失时回退到简化实现，确保在不装 sklearn 的环境下仍能导入核心类 |
| **`python/requirements.txt`** | 新增 `numpy>=1.26.0`、`pandas>=2.0.0`（weight_fusion_engine 依赖） |
| **`python/tests/test_core_paths.py`** | 新增 `Test03FrameworkIntegration`（2 个 case） |

**接入方式**：不修改 DAG 结构，仅在 CompareAgent 内部调用。所有步骤失败安全，不影响主流程。

---

## 三、测试验证结果

```bash
cd python
PYTHONPATH=$(pwd) python3 -m pytest tests/test_core_paths.py -v

# 结果：8 passed, 0 failed
```

---

## 四、给队长的说明

1. **模型 ID 确认**：`.env` 中 `doubao-seed-2.0-lite` 为占位符，如官方模型 ID 带日期后缀（如 `doubao-seed-2.0-lite-250115`），请统一替换。
2. **03 模块依赖**：`numpy` 和 `pandas` 已加入 `requirements.txt`，如比赛环境未预装，可能需要额外安装。
3. **React 前端**：本次未涉及，按定稿报告为"必补"项，需另外安排。

---

## 五、Git 提交建议

```bash
git add -A
git commit -m "feat: 模型统一+反馈闭环修复+核心路径测试+03方案接入

- 统一模型配置为 doubao-seed-2.0-lite（.env/config/client/factory）
- 修复反馈闭环伪闭环：增加 fix_history、partial completion、FixEffectiveness 模型
- 新增核心路径测试：test_core_paths.py（8 case 全过）
- 接入03方案：CompareAgent 集成 weight_fusion_engine + competitive_intelligence_framework
- 增强LLM prompt：情感分析、数据可达性、冲突检测"
```
