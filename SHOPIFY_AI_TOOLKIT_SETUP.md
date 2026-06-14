# Shopify AI Toolkit 接入完成

## ✅ 已完成的配置

### 1. Claude Code 插件 (已安装)
- **状态**: ✅ 已成功安装
- **命令**: `claude plugin install shopify-ai-toolkit@claude-plugins-official`
- **优势**: 自动更新,始终使用最新的 Shopify 能力

### 2. MCP Server (已配置)
- **状态**: ✅ 已配置
- **位置**: `shopify-app/astra-compliance/.mcp.json`
- **配置**:
```json
{
  "mcpServers": {
    "shopify-dev-mcp": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@shopify/dev-mcp@latest"]
    }
  }
}
```

### 3. Shopify App 配置 (已存在)
- **状态**: ✅ 已配置
- **位置**: `shopify-app/astra-compliance/shopify.app.toml`
- **权限 scopes**: `write_products,write_metaobjects,write_metaobject_definitions`

## 📋 下一步操作

### 对于 Claude Agent SDK 二次开发

如果你正在使用 Claude Agent SDK 进行二次开发,可以通过以下方式使用 Shopify AI Toolkit:

#### 方式 1: 使用已安装的 Claude Code 插件
直接在 Claude Code 中,插件会自动加载 Shopify 的所有能力。

#### 方式 2: 在代码中集成 MCP Server
在你的应用中集成 MCP Server:

```javascript
// 示例:在你的 Claude Agent 中使用 Shopify MCP
const shopifyMCPConfig = {
  mcpServers: {
    "shopify-dev-mcp": {
      command: "npx",
      args: ["-y", "@shopify/dev-mcp@latest"]
    }
  }
};
```

#### 方式 3: 使用 Shopify CLI 进行开发
```bash
cd shopify-app/astra-compliance
npm run dev  # 启动开发服务器
shopify app dev  # 使用 Shopify CLI
```

## 🛠️ 可用的 Shopify Skills

通过 AI Toolkit,你可以使用以下能力:

- **shopify-admin**: Admin GraphQL API 查询和变更
- **shopify-functions**: 自定义 Shopify Functions
- **shopify-liquid**: Liquid 模板开发
- **shopify-polaris-***: 各种 Polaris UI 扩展
- **shopify-cli**: Shopify CLI 操作
- **shopify-custom-data**: Metafields 和 Metaobjects

## 📚 相关资源

- [Shopify AI Toolkit 文档](https://shopify.dev/docs/apps/build/ai-toolkit)
- [Shopify CLI 文档](https://shopify.dev/docs/apps/build/cli-for-apps)
- [Shopify Admin API](https://shopify.dev/docs/api/admin-graphql)

## ⚠️ Windows 注意事项

在 Windows 系统上安装完整的 Agent Skills 可能会遇到路径长度限制问题。
已安装的 Claude Code 插件和 MCP Server 不受此限制影响,可以正常使用。

如需在 Windows 上安装 skills,可以:
1. 启用 Windows 长路径支持 (组策略或注册表)
2. 使用 WSL2 (Windows Subsystem for Linux)
3. 仅使用插件和 MCP Server (推荐)
