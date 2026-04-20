# PlotPilot 存储层迁移设计

## 概述

将 PlotPilot 从当前架构（SQLite + FAISS）迁移到全嵌入式三引擎架构（SQLite + LanceDB + FalkorDBLite），通过分层渐进策略实现，保留阶段 2 向 PostgreSQL + LanceDB Cloud + FalkorDB Server 的升级路径。

## 目标架构

```
阶段 1（全嵌入式）
┌─────────────────────────────────────┐
│  SQLite (结构化文档)                  │
│  LanceDB (向量搜索 + 全文检索)        │
│  FalkorDBLite (知识图谱)             │
└─────────────────────────────────────┘

阶段 2（SaaS 化，按需升级）
┌─────────────────────────────────────┐
│  PostgreSQL (结构化，多用户并发)       │
│  LanceDB Cloud (向量，托管)           │
│  FalkorDB Server (图，独立服务)       │
└─────────────────────────────────────┘
```

## 设计约束

- 双产品线：Tauri 桌面端（Windows）+ Docker 服务端，共享同一套应用/领域代码
- 数据迁移：手动触发，旧数据保留作为备份
- 零外部服务进程：阶段 1 所有存储引擎均为嵌入式
- 接口抽象：通过 Protocol 接口隔离存储实现，阶段 2 只需新增实现类

## 迁移策略：分层渐进（方案 A）

三步走，每步可独立验证和回滚：

1. **Step 1 — 接口抽象**：新增 Protocol 定义，现有实现适配新接口，不改行为
2. **Step 2 — FalkorDBLite 知识图谱**：新增图存储实现，替换 SQLite 三元组表
3. **Step 3 — LanceDB 向量存储**：新增 LanceDB 实现，替换 FAISS

---

## Section 1：接口抽象层

### 新增接口

```
domain/
├── ports/                          # 新增目录
│   ├── document_store.py           # 结构化文档存储 Protocol
│   ├── vector_store.py             # 向量存储 Protocol（从 domain/ai/services/ 迁移）
│   ├── graph_store.py              # 图存储 Protocol（新增）
│   └── triple_repository.py        # 三元组仓储 Protocol（新增）
```

### TripleRepositoryProtocol

```python
from typing import Protocol, List, Optional

class TripleRepositoryProtocol(Protocol):
    def persist_triple_sync(self, novel_id: str, triple: "Triple") -> None: ...
    def delete_triple_sync(self, triple_id: str) -> bool: ...
    def get_by_novel_sync(self, novel_id: str) -> List["Triple"]: ...
    def get_by_entity_ids_sync(self, novel_id: str, entity_ids: List[str]) -> List["Triple"]: ...
    def search_by_predicate_sync(self, novel_id: str, predicates: List[str],
                                  subject_ids: Optional[List[str]] = None,
                                  limit: int = 50) -> List["Triple"]: ...
    def get_recent_triples_sync(self, novel_id: str, chapter_number: int,
                                 chapter_range: int = 5, limit: int = 20) -> List["Triple"]: ...
    def traverse_relations(self, novel_id: str, entity_id: str,
                           max_hops: int = 3) -> List["Triple"]: ...
```

### GraphStore Protocol

```python
class GraphStore(Protocol):
    def query(self, graph_name: str, cypher: str, params: dict = None) -> List[dict]: ...
    def execute(self, graph_name: str, cypher: str, params: dict = None) -> None: ...
    def delete_graph(self, graph_name: str) -> None: ...
```

### VectorStore Protocol（修订）

```python
class VectorStore(Protocol):
    async def insert(self, collection: str, id: str, vector: List[float], payload: dict) -> None: ...
    async def search(self, collection: str, query_vector: List[float], limit: int,
                     filter: dict = None) -> List[dict]: ...
    async def delete(self, collection: str, id: str) -> None: ...
    async def update_metadata(self, collection: str, id: str, metadata: dict) -> None: ...
    async def update_metadata_batch(self, collection: str, filter: dict, metadata: dict) -> int: ...
    async def create_collection(self, collection: str, dimension: int) -> None: ...
    async def delete_collection(self, collection: str) -> None: ...
```

变更：移除 `renumber_chapter_metadata_for_novel()`（FAISS 特有 hack），新增 `update_metadata()` 和 `filter` 参数。

### 消费者改造

所有 8+ 个消费 `TripleRepository` 的文件改为依赖 `TripleRepositoryProtocol`，通过 `dependencies.py` 注入。改动量：每个文件改 1-2 行 import + 类型标注。

受影响文件：
- `interfaces/api/dependencies.py`
- `interfaces/api/v1/world/knowledge_graph_routes.py`
- `application/world/services/knowledge_graph_service.py`
- `application/world/services/bible_location_triple_sync.py`
- `application/engine/services/context_builder.py`
- `application/engine/services/background_task_service.py`
- `application/engine/services/chapter_aftermath_pipeline.py`
- `application/world/services/auto_bible_generator.py`

---

## Section 2：FalkorDBLite 知识图谱

### 存储文件

```
data/
├── novels.db              # SQLite（结构化数据，保持不变）
├── novel_graph.db          # FalkorDBLite（知识图谱）
└── lance/                  # LanceDB（向量索引，Section 3）
```

### 图数据模型

每部小说一个独立 graph：`novel_{novel_id}`

```cypher
// 实体节点
(:Entity {
    id: "entity_uuid",
    name: "林黛玉",
    entity_type: "character",       // character/location/item/organization/event
    novel_id: "novel_uuid"
})

// 三元组 → 关系边
(:Entity)-[:RELATION {
    triple_id: "triple_uuid",
    predicate: "爱慕",
    chapter_number: 3,
    confidence: 0.95,
    source_type: "chapter_inferred",
    importance: "high",
    description: "黛玉对宝玉的情感",
    first_appearance: 3,
    note: "...",
    more_chapters: [5, 8, 12],      // 内联 triple_more_chapters
    tags: ["romance", "main_plot"], // 内联 triple_tags
    created_at: "2026-04-20T..."
}]->(:Entity)

// triple_attr 展开为边属性（attr_key → 属性名）
```

### Provenance 建模

```cypher
(:Provenance {
    id: "prov_uuid",
    triple_id: "triple_uuid",
    story_node_id: "sn_uuid",
    chapter_element_id: "ce_uuid",
    rule_id: "acquaintance_rule",
    role: "evidence"
})

(:Provenance)-[:PROVES]->(:Entity)
```

### FalkorDBTripleRepository 核心查询

| 方法 | Cypher |
|------|--------|
| `get_by_novel_sync` | `MATCH (a:Entity)-[r:RELATION]->(b:Entity) WHERE a.novel_id = $nid RETURN a, r, b` |
| `search_by_predicate_sync` | `MATCH (a)-[r:RELATION]->(b) WHERE a.novel_id = $nid AND r.predicate IN $preds RETURN a, r, b LIMIT $limit` |
| `get_by_entity_ids_sync` | `MATCH (e:Entity)-[r:RELATION]-(other) WHERE e.id IN $ids RETURN e, r, other` |
| `traverse_relations` | `MATCH path = (e:Entity {id: $eid})-[:RELATION*1..$hops]-(target) RETURN path` |
| `persist_triple_sync` | `MERGE (a:Entity {id: $sid}) MERGE (b:Entity {id: $oid}) CREATE (a)-[r:RELATION {...}]->(b)` |
| `delete_triple_sync` | `MATCH ()-[r:RELATION {triple_id: $tid}]->() DELETE r` |
| `get_recent_triples_sync` | `MATCH (a)-[r:RELATION]->(b) WHERE a.novel_id = $nid AND r.chapter_number >= $min AND r.chapter_number <= $max RETURN a, r, b ORDER BY r.chapter_number DESC LIMIT $limit` |

### 双模式适配（阶段 2 预留）

```python
# infrastructure/persistence/graph/factory.py
def create_graph_store(config: GraphConfig) -> GraphStore:
    if config.mode == "embedded":
        from redislite.falkordb_client import FalkorDB
        return FalkorDBLiteGraphStore(FalkorDB(config.db_path))
    else:
        from falkordb import FalkorDB
        return FalkorDBServerGraphStore(FalkorDB(host=config.host, port=config.port))
```

---

## Section 3：LanceDB 向量存储

### 数据模型

```python
from lancedb.pydantic import Vector, LanceModel

class VectorRecord(LanceModel):
    id: str
    collection: str
    novel_id: str
    chapter_number: int = -1
    kind: str                       # 'chapter_summary' / 'triple' / 'bible_snippet'
    text: str
    vector: Vector(1536)            # 维度由 embedding 模型决定
    triple_id: str = ""
    subject: str = ""
    predicate: str = ""
    object: str = ""
```

每个 collection 对应一张 LanceDB table：`novel_{novel_id}_chunks`、`novel_{novel_id}_triples`。

### LanceVectorStore 实现

```python
class LanceVectorStore(VectorStore):
    def __init__(self, db_path: str):
        self._db = lancedb.connect(db_path)

    async def insert(self, collection: str, id: str, vector: List[float], payload: dict):
        table = self._get_or_create_table(collection, len(vector))
        table.add([{"id": id, "vector": vector, **payload}])

    async def search(self, collection: str, query_vector: List[float],
                     limit: int, filter: dict = None) -> List[dict]:
        table = self._db.open_table(collection)
        query = table.search(query_vector).limit(limit)
        if filter:
            query = query.where(self._build_filter(filter))
        return query.to_list()

    async def delete(self, collection: str, id: str):
        table = self._db.open_table(collection)
        table.delete(f"id = '{id}'")

    async def update_metadata(self, collection: str, id: str, metadata: dict):
        table = self._db.open_table(collection)
        table.update(where=f"id = '{id}'", values=metadata)

    async def create_collection(self, collection: str, dimension: int):
        if collection not in self._db.table_names():
            self._db.create_table(collection, schema=self._schema_for_dim(dimension))

    async def delete_collection(self, collection: str):
        if collection in self._db.table_names():
            self._db.drop_table(collection)
```

### 对比 FAISS 的改进

| 维度 | FAISS 现状 | LanceDB |
|------|-----------|---------|
| 元数据过滤 | 全量加载后内存过滤 | SQL WHERE 子句 |
| 删除 | 软删除，文件膨胀 | 真删除 |
| 全文检索 | 无 | 内置 BM25 FTS |
| 混合搜索 | 不支持 | `query_type="hybrid"` |
| 章节重编号 | 自定义 renumber hack | `table.update(where=..., values=...)` |
| 维度变更 | 重建整个集合 | 新建 table |
| 事务 | 无 | Lance 格式支持版本化 |

### 章节重编号简化

```python
# ChapterIndexingService
def renumber_chapters(self, novel_id: str, mapping: Dict[int, int]):
    for old_num, new_num in mapping.items():
        await self._vec_store.update_metadata_batch(
            collection=f"novel_{novel_id}_chunks",
            filter={"novel_id": novel_id, "chapter_number": old_num},
            metadata={"chapter_number": new_num}
        )
```

---

## Section 4：数据迁移

### 迁移触发方式

用户手动触发（设置页面按钮 / CLI 命令），旧数据保留作为备份。

### 迁移脚本设计

```python
# scripts/migrate_to_v2_storage.py

class StorageMigration:
    """从 SQLite triples + FAISS 迁移到 FalkorDBLite + LanceDB"""

    def migrate_knowledge_graph(self, novel_id: str):
        """SQLite triples → FalkorDBLite"""
        # 1. 从 SQLite 读取所有三元组 + 子表数据
        triples = self._sqlite_repo.get_by_novel_sync(novel_id)
        side_data = self._sqlite_repo.get_triple_side_data_for_novel(novel_id)

        # 2. 构建实体去重集合
        entities = self._extract_unique_entities(triples)

        # 3. 批量写入 FalkorDB
        graph_name = f"novel_{novel_id}"
        for entity in entities:
            self._graph.execute(graph_name,
                "MERGE (:Entity {id: $id, name: $name, entity_type: $type, novel_id: $nid})",
                params=entity)

        for triple in triples:
            self._graph.execute(graph_name,
                """MATCH (a:Entity {id: $sid}), (b:Entity {id: $oid})
                   CREATE (a)-[:RELATION {triple_id: $tid, predicate: $pred, ...}]->(b)""",
                params=self._triple_to_params(triple, side_data))

        # 4. 迁移 provenance
        self._migrate_provenance(novel_id, graph_name)

    def migrate_vectors(self, novel_id: str):
        """FAISS → LanceDB"""
        # 1. 从 FAISS 读取所有向量 + 元数据
        collections = [f"novel_{novel_id}_chunks", f"novel_{novel_id}_triples"]
        for coll in collections:
            items = self._faiss_store.get_all_items(coll)
            if not items:
                continue

            # 2. 批量写入 LanceDB
            records = [{"id": item["id"], "vector": item["vector"], **item["payload"]}
                       for item in items]
            table = self._lance_db.create_table(coll, data=records)

            # 3. 创建 FTS 索引
            table.create_fts_index("text")

    def run(self, novel_ids: List[str] = None):
        """执行完整迁移"""
        if novel_ids is None:
            novel_ids = self._get_all_novel_ids()

        for novel_id in novel_ids:
            print(f"迁移小说 {novel_id}...")
            self.migrate_knowledge_graph(novel_id)
            self.migrate_vectors(novel_id)
            print(f"  完成 ✓")

        # 标记迁移完成（写入 config）
        self._mark_migration_complete()
```

### 迁移流程

```
1. 用户点击"升级存储引擎"按钮
2. 前端确认对话框（提示备份）
3. 后端调用 StorageMigration.run()
4. 逐小说迁移：SQLite triples → FalkorDB，FAISS → LanceDB
5. 写入迁移标记到 config
6. 下次启动时 DI 工厂读取标记，使用新存储实现
7. 旧文件保留在 data/backup/ 目录
```

### 回滚方案

- 删除 `data/novel_graph.db` 和 `data/lance/` 目录
- 清除迁移标记
- 系统自动回退到 SQLite + FAISS 实现

---

## Section 5：文件结构总览

```
infrastructure/
├── persistence/
│   ├── database/                    # 现有 SQLite 实现（保留）
│   │   ├── sqlite_knowledge_repository.py
│   │   ├── triple_repository.py     # 适配 TripleRepositoryProtocol
│   │   └── ...
│   ├── graph/                       # 新增：图存储
│   │   ├── falkordb_lite_store.py   # GraphStore 嵌入式实现
│   │   ├── falkordb_server_store.py # GraphStore 服务端实现（阶段 2）
│   │   └── falkordb_triple_repository.py  # TripleRepositoryProtocol 图实现
│   └── lance/                       # 新增：向量存储
│       └── lance_vector_store.py    # VectorStore LanceDB 实现
├── ai/
│   └── chromadb_vector_store.py     # 保留，迁移前仍可用
├── config/
│   └── storage_factory.py           # 新增：存储层工厂

domain/
├── ports/                           # 新增：端口接口
│   ├── document_store.py            # 阶段 2 预留，本次不实现
│   ├── vector_store.py
│   ├── graph_store.py
│   └── triple_repository.py

scripts/
├── migrate_to_v2_storage.py         # 新增：迁移脚本
```

---

## Section 6：环境变量与配置

```env
# .env
STORAGE_VERSION=v1                   # v1=旧架构, v2=新架构（迁移后自动切换）

# FalkorDB
GRAPH_DB_PATH=./data/novel_graph.db  # 嵌入式模式
# FALKORDB_HOST=localhost            # 服务端模式（阶段 2）
# FALKORDB_PORT=6379

# LanceDB
LANCE_DB_PATH=./data/lance           # 嵌入式模式
# LANCEDB_URI=db://...              # LanceDB Cloud（阶段 2）

# PostgreSQL（阶段 2）
# DATABASE_URL=postgresql://...
```

---

## 实施顺序

1. **Step 1**：新增 `domain/ports/` 接口定义 + 现有实现适配（不改行为）
2. **Step 2**：实现 `FalkorDBLiteGraphStore` + `FalkorDBTripleRepository`
3. **Step 3**：实现 `LanceVectorStore`
4. **Step 4**：实现 `storage_factory.py` + DI 切换逻辑
5. **Step 5**：实现迁移脚本 + 前端迁移按钮
6. **Step 6**：测试（单元测试 + 集成测试 + 迁移测试）

## 新增依赖

```
# requirements.txt 新增
falkordblite>=0.1.0
lancedb>=0.6.0
```

## 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| FalkorDBLite Windows 兼容性 | 提前在 Windows CI 验证；备选 networkx 纯 Python 降级 |
| LanceDB API 变更（较新库） | 锁定版本；封装在 VectorStore 接口后隔离 |
| 迁移脚本数据丢失 | 旧数据保留不删除；迁移前自动备份 |
| 性能回归 | 迁移后跑基准测试对比 FAISS 查询延迟 |
