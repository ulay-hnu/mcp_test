# MCP (Model Control Protocol) 客户端

## 项目简介
这是一个基于Python实现的MCP（Model Control Protocol）客户端，用于与OpenAI API进行交互并支持本地工具调用的应用程序。该客户端支持异步操作，可以连接到Python或JavaScript编写的MCP服务器。

## 功能特点
- 支持与OpenAI API的异步通信
- 支持本地MCP工具的调用和管理
- 支持Python和JavaScript编写的服务器脚本
- 提供交互式命令行界面
- 支持Function Calling功能
- 自动进行JSON格式转换

## 环境要求
- Python 3.7+
- 异步支持 (asyncio)
- OpenAI Python SDK
- python-dotenv

## 安装依赖
```bash
# 使用 uv 安装依赖（推荐）
uv pip install openai python-dotenv mcp-python

# 或使用 pip 安装依赖
pip install openai python-dotenv mcp-python
```

## 环境变量配置
在项目根目录创建 `.env` 文件，并配置以下环境变量：
```env
OPENAI_API_KEY=你的OpenAI API密钥
BASE_URL=https://api.openai.com/v1  # 可选，默认为OpenAI官方API地址
MODEL=gpt-3.5-turbo  # 可选，默认使用gpt-3.5-turbo
```

## 使用方法
1. 启动客户端：
```bash
uv run mcpclient.py <server_script_path>
```
例如：
```bash
uv run mcpclient.py server.py
```

2. 交互式使用：
- 启动后，按照提示输入消息
- 输入 'quit' 退出程序

## 主要类和方法

### MCPClient
主要的客户端类，包含以下方法：

#### `__init__()`
- 初始化MCP客户端
- 加载环境变量
- 设置OpenAI客户端

#### `connect_to_server(server_script_path: str)`
- 连接到指定的MCP服务器
- 支持.py和.js格式的服务器脚本
- 初始化通信会话

#### `process_query(query: str)`
- 处理用户输入的查询
- 调用OpenAI API
- 处理工具调用

#### `transform_json(json2_data)`
- 转换Claude格式的Function Calling参数为OpenAI格式
- 处理工具调用的参数转换

#### `chat_loop()`
- 提供交互式命令行界面
- 处理用户输入
- 显示AI响应

## 错误处理
- 环境变量缺失检查
- API调用异常处理
- 服务器连接异常处理
- 用户输入验证

## 注意事项
1. 确保正确设置环境变量
2. 确保服务器脚本可用且格式正确
3. 保持网络连接稳定
4. API密钥权限和额度管理

## 开发计划
- [ ] 添加更多工具支持
- [ ] 改进错误处理机制
- [ ] 添加日志系统
- [ ] 支持更多模型选项
- [ ] 优化性能和响应速度

## 贡献指南
欢迎提交Issue和Pull Request来改进这个项目。

## 许可证
[添加您的许可证信息]
