import asyncio
import json
import os
import sys
from http.client import responses
from typing import Optional
from contextlib import AsyncExitStack
from zoneinfo import available_timezones

from openai import OpenAI
from dotenv import load_dotenv
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client


load_dotenv()

class MCPClient:
    def __init__(self):
        """初始化 MCP 客户端"""
        self.exit_stack = AsyncExitStack()
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("BASE_URL")
        self.model = os.getenv("MODEL")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY 未设置")
        self.client = OpenAI(api_key=self.openai_api_key,base_url=self.base_url)
        self.session: Optional[ClientSession] = None

    async def transform_json(self,json2_data):
        """
        将claude Function calling参数格式转化为openai
        Function calling参数格式，多余字段会被直接删除。

         :param json2_data:一个可被解释为列表的 python 对象（或已解析的JSON 数据）
         :return: 转换后的新列表
         """
        result = json2_data

        for item in json2_data:
            # 确保有“type” 和 “function”两个关键字段
            if not isinstance(item, dict) or "type" not in item or "function" not in item:
                continue

            old_func = item["function"]

            # 确保function 下有我们需要的关键子字段
            if not isinstance(old_func, dict) or "name" not in old_func or "description" not in old_func:
                continue

            #处理function字段
            new_func = {
                "name": old_func["name"],
                "description": old_func["description"],
                "parameters": {}
            }

            #读取 input_schema 并转成parameters
            if "input_schema" in old_func and isinstance(old_func["input_schema"], dict):
               old_schema = old_func["input_schema"]

    # 新的parameters 保留type，properties，required字段
               new_func["parameters"]["type"] = old_schema.get("type", "object")
               new_func["parameters"]["properties"] = old_schema.get("properties", {})
               new_func["parameters"]["required"] = old_schema.get("required", [])

            new_item = {
                "type": item["type"],
                "function": new_func
            }

            result.append(new_item)
        return result
    async def connect_to_server(self,server_script_path: str):
        """连接到MCP 服务器并列出可用工具"""
        is_python = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
        if not (is_python or is_js):
            raise ValueError("服务器脚本必须是 .py 或 .js 文件")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )

        #启动 MCP 服务器并建立通信
        stdio_transport = await (
            self.exit_stack.enter_async_context(stdio_client(server_params)))
        self.stdio, self.write = stdio_transport
        self.session = await (
            self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write)))

        await self.session.initialize()

        # 获取服务器上可用的工具列表
        response = await self.session.list_tools()
        tools = response.tools
        print("\n已连接到服务器，支持一下工具", [tool.name for tool in tools])

    async def process_query(self, query: str) -> str:
        """
        使用大模型处理查询并调用可用的MCP 工具 {Function Callinng}
        """
        messages = [{"role": "user", "content": query}]

        response = await self.session.list_tools()

        available_tools= [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
        } for tool in response.tools]
        #print(available_tools)

        #进行参数格式转化
        available_tools = await  self.transform_json(available_tools)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=available_tools,
        )

        #处理返回的内容
        content = response.choices[0]
        if content.finish_reason =="tool_calls":
            #如果是需要使用工具，就解析工具
            tool_call = content.message.tool_calls[0]
            tool_name = tool_call.tool.name
            tool_args = json.loads(tool_call.function.arguments)

            #执行工具
            result = await self.session.call_tool(tool_name, tool_args)
            print(f"\n\n[Calling tool {tool_name} with arguments {tool_args}]\n\n")

            #将模型返回的调用哪个工具数据和工具执行完成后的数据都存入messages中
            messages.append(content.message.model_dump())
            messages.append({
                "role": "tool",
                "content": result.content[0].text,
                "tool_call_id": tool_call.id,
            })
            # 将上面的结果再返回给大模型用于生产最终的结果
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            return response.choices[0].message.content

        return content.message.content
    async def chat_loop(self):
        """运行交互式聊天循环"""
        print("\n MCP 客户端已启动 请输入 'quit' 退出")

        while True:
            try:
                user_input = input("\n\n请输入您的消息：").strip()
                if user_input.lower() == "quit":
                    break

                    response = await self.process_query(user_input)    #发送用户输入到OpenAI API
                    print(f"\n OpenAI: {response}")

            except Exception as e:
                print(f"发生错误: str{e}")
    async def cleanup(self):
        """清理资源"""
        await self.exit_stack.aclose()

async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py<path_to_server_script>")
        sys.exit(1)

    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())