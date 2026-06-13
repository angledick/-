# 通用Manager提示模板

<cite>
**本文档引用的文件**
- [manager_generic.yaml](file://backend/data/prompts/manager_generic.yaml)
- [manager_agent.py](file://backend/app/core/manager_agent.py)
- [agent_config.py](file://backend/app/api/agent_config.py)
- [agent_crud.py](file://backend/app/api/agent_crud.py)
- [prompt_loader.py](file://backend/app/services/prompt_loader.py)
- [AgentEditModal.tsx](file://frontend/src/components/config/AgentEditModal.tsx)
- [AgentConfigCard.tsx](file://frontend/src/components/config/AgentConfigCard.tsx)
- [AgentMonitorPage.tsx](file://frontend/src/pages/AgentMonitorPage.tsx)
</cite>

## 目录
1. [简介](#简介)
2. [项目结构](#项目结构)
3. [核心组件](#核心组件)
4. [架构概览](#架构概览)
5. [详细组件分析](#详细组件分析)
6. [依赖关系分析](#依赖关系分析)
7. [性能考虑](#性能考虑)
8. [故障排除指南](#故障排除指南)
9. [结论](#结论)

## 简介

通用Manager提示模板是Astra合规智能体系统中的核心组件，负责为Manager Agent提供标准化的system prompt模板。该模板确保Manager Agent能够正确理解其职责、执行原则和输出格式要求，从而有效地协调多个Worker Agent完成复杂的合规任务。

系统采用分层架构设计，包含前端配置界面、后端API服务、Manager Agent协调器和Worker Agent执行器等组件。通用提示模板作为系统的基础配置之一，为整个智能体生态系统提供了统一的行为规范和输出标准。

## 项目结构

该项目采用前后端分离的架构设计，主要分为以下层次：

```mermaid
graph TB
subgraph "前端层"
FE1[Agent配置界面]
FE2[Agent监控页面]
FE3[实时聊天界面]
end
subgraph "后端API层"
API1[Agent CRUD API]
API2[Agent执行API]
API3[事件处理API]
end
subgraph "核心服务层"
CORE1[Manager Agent]
CORE2[Worker Registry]
CORE3[Task Decomposer]
CORE4[Prompt Loader]
end
subgraph "数据存储层"
DATA1[Agent配置存储]
DATA2[Prompt模板存储]
DATA3[任务状态存储]
end
FE1 --> API1
FE2 --> API1
FE3 --> API2
API1 --> CORE1
API2 --> CORE1
CORE1 --> CORE2
CORE1 --> CORE3
CORE1 --> CORE4
CORE1 --> DATA1
CORE4 --> DATA2
```

**图表来源**
- [manager_agent.py:120-150](file://backend/app/core/manager_agent.py#L120-L150)
- [agent_crud.py:13-28](file://backend/app/api/agent_crud.py#L13-L28)
- [agent_config.py:9-16](file://backend/app/api/agent_config.py#L9-L16)

**章节来源**
- [manager_agent.py:1-16](file://backend/app/core/manager_agent.py#L1-L16)
- [agent_crud.py:1-11](file://backend/app/api/agent_crud.py#L1-L11)
- [agent_config.py:1-7](file://backend/app/api/agent_config.py#L1-L7)

## 核心组件

### Manager Agent协调器

Manager Agent是多Agent系统的协调中心，负责接收高层任务、拆解子任务、分配Worker Agent并监控执行进度。其核心职责包括：

- **任务拆解**：将复杂任务分解为可执行的子任务
- **Worker分配**：根据业务阶段和优先级选择最适合的Worker
- **执行协调**：管理子任务的执行顺序和依赖关系
- **进度监控**：跟踪任务执行状态并提供用户干预能力

### 通用提示模板系统

通用提示模板系统提供了标准化的system prompt模板，确保所有Manager Agent具有统一的行为规范：

- **执行原则**：明确Agent的执行准则和约束条件
- **输出格式**：规定标准化的JSON输出格式
- **错误处理**：定义错误情况下的处理方式
- **上下文管理**：指导如何处理任务上下文信息

### 前端配置界面

前端提供了完整的Agent配置和管理系统，包括：

- **Agent编辑**：支持创建、修改和删除Agent配置
- **实时预览**：提供system prompt的实时预览功能
- **状态管理**：显示Agent的启用状态和执行统计
- **批量操作**：支持批量启用/禁用和排序调整

**章节来源**
- [manager_agent.py:120-150](file://backend/app/core/manager_agent.py#L120-L150)
- [manager_generic.yaml:1-24](file://backend/data/prompts/manager_generic.yaml#L1-L24)
- [AgentEditModal.tsx:105-134](file://frontend/src/components/config/AgentEditModal.tsx#L105-L134)

## 架构概览

系统采用事件驱动的异步架构，Manager Agent作为中央协调器连接各个组件：

```mermaid
sequenceDiagram
participant User as 用户
participant Frontend as 前端界面
participant API as 后端API
participant Manager as Manager Agent
participant Worker as Worker Agent
participant Storage as 数据存储
User->>Frontend : 提交任务请求
Frontend->>API : 发送API请求
API->>Manager : 创建任务组
Manager->>Manager : 拆解子任务
Manager->>Worker : 分配任务
Worker->>Storage : 读取配置
Worker->>Worker : 执行任务
Worker->>Manager : 返回结果
Manager->>API : 汇总结果
API->>Frontend : 返回响应
Frontend->>User : 显示结果
Note over Manager,Worker : 异步执行和监控
```

**图表来源**
- [manager_agent.py:169-227](file://backend/app/core/manager_agent.py#L169-L227)
- [agent_crud.py:126-163](file://backend/app/api/agent_crud.py#L126-L163)

**章节来源**
- [manager_agent.py:309-397](file://backend/app/core/manager_agent.py#L309-L397)
- [agent_config.py:24-38](file://backend/app/api/agent_config.py#L24-L38)

## 详细组件分析

### Manager Agent类结构

```mermaid
classDiagram
class ManagerAgent {
+dict~str,TaskGroup~ _task_groups
+WorkerRegistry workers
+TaskDecomposer decomposer
+dict~str,str[]~ _worker_tasks
+AgentMessage[] _message_log
+submit_task(task, context, created_by) TaskGroup
+execute_group(group_id) Dict~str,Any~
+monitor_progress(group_id) Dict~str,Any~
+user_intervention(group_id, action, subtask_id, reason) Dict~str,Any~
+get_worker_status() Dict[]str,Any~~
-_find_best_worker(SubTask) WorkerDefinition
-_execute_subtask(TaskGroup, SubTask) Dict~str,Any~
-_run_worker(SubTask) Dict~str,Any~
-_record_message(AgentMessage) void
}
class TaskGroup {
+string group_id
+string task_description
+dict~str,Any~ context
+SubTask[] subtasks
+string status
+string created_at
+string conversation_id
+to_dict() Dict~str,Any~
+_calc_progress() Dict~str,Any~
}
class AgentMessage {
+string message_id
+string sender
+string receiver
+string message_type
+dict~str,Any~ payload
+string timestamp
+string conversation_id
+to_dict() Dict~str,Any~
}
ManagerAgent --> TaskGroup : manages
ManagerAgent --> AgentMessage : records
TaskGroup --> SubTask : contains
```

**图表来源**
- [manager_agent.py:37-117](file://backend/app/core/manager_agent.py#L37-L117)
- [manager_agent.py:120-166](file://backend/app/core/manager_agent.py#L120-L166)

### 通用提示模板结构

通用提示模板采用YAML格式定义，包含以下关键要素：

```mermaid
flowchart TD
Template[提示模板] --> SystemPrompt[System Prompt]
Template --> ExecutionPrinciples[执行原则]
Template --> OutputFormat[输出格式]
Template --> ErrorHandling[错误处理]
SystemPrompt --> RoleDefinition[角色定义]
SystemPrompt --> TaskDescription[任务描述]
ExecutionPrinciples --> Principle1[严格按指令执行]
ExecutionPrinciples --> Principle2[使用可用工具]
ExecutionPrinciples --> Principle3[生成结构化报告]
ExecutionPrinciples --> Principle4[信息不足时说明]
OutputFormat --> JSONFormat[JSON格式]
OutputFormat --> StatusField[状态字段]
OutputFormat --> SummaryField[摘要字段]
OutputFormat --> DetailsField[详情字段]
OutputFormat --> RecommendationsField[建议字段]
ErrorHandling --> NotFound[信息不足]
ErrorHandling --> ErrorProcessing[处理错误]
ErrorHandling --> RetryLogic[重试机制]
```

**图表来源**
- [manager_generic.yaml:4-23](file://backend/data/prompts/manager_generic.yaml#L4-L23)

**章节来源**
- [manager_generic.yaml:1-24](file://backend/data/prompts/manager_generic.yaml#L1-L24)
- [manager_agent.py:475-594](file://backend/app/core/manager_agent.py#L475-L594)

### 前端Agent配置界面

前端提供了直观的Agent配置界面，支持实时编辑和预览：

```mermaid
graph LR
subgraph "Agent配置界面"
EditModal[Agent编辑弹窗]
TypeSelect[类型选择]
Description[描述输入]
SystemPrompt[System Prompt编辑]
Preview[预览区域]
Actions[操作按钮]
end
subgraph "数据流"
EditModal --> TypeSelect
EditModal --> Description
EditModal --> SystemPrompt
SystemPrompt --> Preview
EditModal --> Actions
end
subgraph "后端交互"
Actions --> APICall[API调用]
APICall --> Server[后端服务器]
Server --> Storage[配置存储]
end
```

**图表来源**
- [AgentEditModal.tsx:105-134](file://frontend/src/components/config/AgentEditModal.tsx#L105-L134)
- [AgentConfigCard.tsx:30-52](file://frontend/src/components/config/AgentConfigCard.tsx#L30-L52)

**章节来源**
- [AgentEditModal.tsx:105-134](file://frontend/src/components/config/AgentEditModal.tsx#L105-L134)
- [AgentConfigCard.tsx:30-52](file://frontend/src/components/config/AgentConfigCard.tsx#L30-L52)

## 依赖关系分析

系统各组件之间的依赖关系如下：

```mermaid
graph TB
subgraph "外部依赖"
YAML[YAML解析器]
JSON[JSON处理器]
AsyncIO[异步I/O]
FastAPI[Web框架]
end
subgraph "内部模块"
PromptLoader[Prompt加载器]
ManagerAgent[Manager Agent]
WorkerRegistry[Worker注册表]
TaskDecomposer[任务分解器]
AgentAPI[Agent API]
AgentCRUD[Agent CRUD]
end
subgraph "数据存储"
AgentStore[Agent配置存储]
PromptStore[Prompt模板存储]
TaskStore[任务状态存储]
end
YAML --> PromptLoader
JSON --> PromptLoader
AsyncIO --> ManagerAgent
FastAPI --> AgentAPI
FastAPI --> AgentCRUD
PromptLoader --> ManagerAgent
WorkerRegistry --> ManagerAgent
TaskDecomposer --> ManagerAgent
AgentAPI --> ManagerAgent
AgentCRUD --> AgentStore
ManagerAgent --> WorkerRegistry
ManagerAgent --> TaskStore
AgentAPI --> AgentStore
AgentCRUD --> AgentStore
PromptLoader --> PromptStore
```

**图表来源**
- [prompt_loader.py:44-78](file://backend/app/services/prompt_loader.py#L44-L78)
- [manager_agent.py:27-31](file://backend/app/core/manager_agent.py#L27-L31)
- [agent_crud.py:18-26](file://backend/app/api/agent_crud.py#L18-L26)

**章节来源**
- [prompt_loader.py:44-78](file://backend/app/services/prompt_loader.py#L44-L78)
- [manager_agent.py:27-31](file://backend/app/core/manager_agent.py#L27-L31)

## 性能考虑

系统在设计时充分考虑了性能优化：

### 异步执行模型
- 使用asyncio实现非阻塞的并发执行
- 支持多个子任务的并行处理
- 异常处理不影响其他任务的执行

### 缓存机制
- Prompt模板采用内存缓存减少磁盘I/O
- Worker状态信息缓存提高查询效率
- 任务结果缓存支持快速检索

### 资源管理
- Worker负载均衡避免资源过载
- 任务超时控制防止资源泄露
- 连接池管理数据库连接

## 故障排除指南

### 常见问题及解决方案

**Manager Agent无法启动**
- 检查Worker注册表是否正常
- 验证任务分解器配置
- 确认数据库连接状态

**任务执行失败**
- 查看子任务错误日志
- 检查Worker可用性
- 验证工具和技能配置

**提示模板加载失败**
- 确认YAML文件语法正确
- 检查文件权限设置
- 验证模板路径配置

**前端配置界面异常**
- 检查API接口连通性
- 验证用户权限设置
- 确认浏览器兼容性

**章节来源**
- [manager_agent.py:444-473](file://backend/app/core/manager_agent.py#L444-L473)
- [prompt_loader.py:44-78](file://backend/app/services/prompt_loader.py#L44-L78)

## 结论

通用Manager提示模板系统为Astra合规智能体提供了标准化的配置框架，通过清晰的角色定义、严格的执行原则和规范的输出格式，确保了整个智能体生态系统的协调一致性和可维护性。

该系统的设计体现了现代AI应用的最佳实践：
- **模块化设计**：各组件职责明确，便于独立开发和测试
- **异步架构**：支持高并发和高性能的执行模式
- **配置驱动**：通过模板和配置实现灵活的功能扩展
- **可观测性**：完善的日志记录和状态监控机制

未来可以进一步优化的方向包括：
- 增强模板的动态渲染能力
- 扩展更多类型的提示模板
- 优化性能监控和告警机制
- 加强安全性和访问控制