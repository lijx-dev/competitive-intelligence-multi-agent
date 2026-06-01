"""
Palantir Ontology 关系图谱测试 — 覆盖节点创建、关系建立、图谱构建。
"""
import pytest

from src.core.ontology_relation_graph import (
    OntologyGraph,
    OntologyNode,
    OntologyRelation,
    RelationType,
    build_demo_graph,
)


class TestOntologyNode:
    """Ontology 节点基础操作"""

    def test_node_creation(self):
        """节点创建后属性正确"""
        node = OntologyNode(
            id="comp_001",
            label="TestCorp",
            layer="L1",
            entity_type="Competitor",
            color="#3B82F6",
            size=28,
        )
        assert node.id == "comp_001"
        assert node.label == "TestCorp"
        assert node.layer == "L1"
        assert node.entity_type == "Competitor"


class TestOntologyGraph:
    """关系图谱 CRUD"""

    def test_empty_graph(self):
        """空图谱结构正确"""
        graph = OntologyGraph.empty()
        assert graph.nodes == []
        assert graph.relations == []
        assert graph.generated_at == ""

    def test_add_nodes(self):
        """添加节点后nodes列表增长"""
        graph = OntologyGraph.empty()
        node = OntologyNode(id="comp_001", label="TestCorp", layer="L1", entity_type="Competitor", color="#3B82F6", size=28)
        graph.nodes.append(node)
        assert len(graph.nodes) == 1
        assert graph.nodes[0].label == "TestCorp"

    def test_add_relations(self):
        """添加关系后relations列表增长"""
        graph = OntologyGraph.empty()
        rel = OntologyRelation(
            id="rel_001",
            source="comp_001",
            target="prod_001",
            relation_type=RelationType.COMPETITOR_HAS_PRODUCT,
            label="提供",
        )
        graph.relations.append(rel)
        assert len(graph.relations) == 1
        assert graph.relations[0].relation_type == RelationType.COMPETITOR_HAS_PRODUCT

    def test_demo_graph_structure(self):
        """Demo 图谱必须包含节点和关系"""
        graph = build_demo_graph("测试竞品")
        assert len(graph.nodes) > 0
        assert len(graph.relations) > 0
        # 检查节点ID唯一性
        ids = [n.id for n in graph.nodes]
        assert len(ids) == len(set(ids))

    def test_relation_type_enum(self):
        """关系类型枚举值必须合法"""
        assert RelationType.COMPETITOR_HAS_PRODUCT == "competitor_has_product"
        assert RelationType.PRODUCT_HAS_FEATURE == "product_has_feature"
        assert isinstance(RelationType.COMPETITOR_HAS_PRODUCT, str)
