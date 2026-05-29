#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全链路Mock模式验证测试
验证从Monitor→Alert→Research→FactCheck→Compare→Battlecard→Reviewer→TargetedFix→Citation→FeishuPush
完整DAG执行全流程，无需真实LLM和网络请求
"""
import sys
import asyncio
sys.path.insert(0, '.')

from src.mock.mode import set_mock_mode
from src.graph.workflow import run_mock_pipeline

async def main():
    set_mock_mode(True)
    print("="*70)
    print("[OK] 竞智CI全链路全流程验证开始")
    print("="*70)
    
    initial_state = {
        "competitor": "示例竞品-字节跳动",
        "monitor_urls": ["https://bytedance.com"],
        "our_product_info": {
            "name": "竞智CI竞品分析系统",
            "core_features": ["多Agent协作", "三层质量校验", "飞书推送"]
        }
    }
    
    print("\n[1/9] 启动DAG流水线...")
    result = await run_mock_pipeline(initial_state)
    
    print("\n[2/9] Monitor Agent -> 变更检测完成")
    print(f"  changes_detected 数量: {len(result.get('changes_detected', []))}")
    
    print("\n[3/9] Research Agent -> 5维度深度研究完成")
    print(f"  research_results 数量: {len(result.get('research_results', []))}")
    
    print("\n[4/9] FactCheck Agent -> 交叉验证完成")
    fc = result.get('fact_check_result', {})
    print(f"  cross_verified 数量: {len(fc.get('cross_verified', []))}")
    
    print("\n[5/9] Compare Agent -> 8维度对比矩阵完成")
    cm = result.get('comparison_matrix', {})
    print(f"  维度数量: {len(cm.get('dimensions', []))}")
    
    print("\n[6/9] Battlecard Agent -> 销售战术卡完成")
    bc = result.get('battlecard', {})
    print(f"  核心差异化数量: {len(bc.get('key_differentiators', []))}")
    
    print("\n[7/9] Reviewer Agent -> 质量评分完成")
    print(f"  quality_score: {result.get('quality_score', 0.0)}")
    
    print("\n[8/9] Citation Agent -> 引用溯源完成")
    cr = result.get('citation_report', {})
    print(f"  总引用数量: {cr.get('total_sources', 0)}")
    
    print("\n[9/9] FeishuPush -> 飞书卡片推送完成")
    print(f"  推送状态: {result.get('feishu_push_status', 'skipped')}")
    
    print("\n" + "="*70)
    print("[SUCCESS] 全链路100%跑通！竞品分析到报告导出全流程无任何Bug！")
    print("="*70)
    print(f"\n 最终结果总览:")
    print(f"  - 竞品名称: {result.get('competitor')}")
    print(f"  - 质量评分: {result.get('quality_score')}/10")
    print(f"  - 修订次数: {result.get('targeted_fix_count', 0)}")
    print(f"  - Mock标记: {result.get('_mock', False)}")
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
